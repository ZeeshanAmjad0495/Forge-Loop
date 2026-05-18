"""OpenHands local execution service.

Controlled, workspace-scoped, approval-gated, audited execution of the
OpenHands CLI inside a registered workspace. Subprocess invocation is
deliberately narrow: a single configured command, no shell, minimal env,
timeout-bounded, output-size-bounded. Changed-file evidence is gathered by
metadata-only filesystem snapshots — never by git.

Public entry point: ``OpenHandsExecutionService.execute(dev_task_id, body,
actor_email)``. ``dry_run`` mode delegates to ``openhands_workflow``; ``local``
mode requires ``config.OPENHANDS_EXECUTION_ENABLED=true`` and an approved
approval.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException
from pydantic import BaseModel

from .. import config as _config
from . import artifact_storage as _storage
from ..models import (
    Approval,
    Artifact,
    OpenHandsChangedPath,
    OpenHandsExecuteRequest,
    OpenHandsExecuteResponse,
    OpenHandsExecutionSummary,
    OpenHandsInstructionPackage,
    OpenHandsPreparePackageRequest,
    OpenHandsPrepareResponse,
    ToolRun,
    ToolRunConclusion,
    ToolRunStatus,
)
from ..tool_runners.openhands import build_openhands_instruction_package
from . import openhands_workflow, workspace_snapshot

TRUNCATION_MARKER = "\n...[truncated]"
TAIL_BYTES = 2000

# Upstream OpenHands conversation execution_status values that mean the
# agent loop has ended. Anything outside this set (or ``None``) is treated
# as "still running" — we then defer to the event-count quiet-after
# heuristic.
_TERMINAL_EXECUTION_STATUSES = frozenset({
    "finished",
    "failed",
    "cancelled",
    "stopped",
    "error",
    "completed",
})


class OpenHandsExecutionResult(BaseModel):
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    # B3 latency attribution. For the HTTP bridge executor these split the
    # total wall time into the sandbox/runtime spin-up phase (POST +
    # start-task -> READY) and the agent-run phase (event-poll loop /
    # inference). Both default 0.0 for executors that don't measure phases
    # (subprocess executor, dry-run) — 0.0 means "single-phase / unmeasured".
    resolve_seconds: float = 0.0
    run_seconds: float = 0.0
    error: str | None = None


class OpenHandsExecutor(Protocol):
    def run(
        self,
        *,
        command: str,
        args: list[str],
        cwd: str,
        timeout_seconds: int,
        max_output_bytes: int,
        working_directory: str | None = None,
        title: str | None = None,
    ) -> OpenHandsExecutionResult: ...


def _truncate(text: str, cap: int) -> str:
    if cap <= 0:
        return ""
    if len(text) <= cap:
        return text
    head = text[: max(0, cap - len(TRUNCATION_MARKER))]
    return head + TRUNCATION_MARKER


def _tail(text: str, cap: int = TAIL_BYTES) -> str:
    if not text:
        return ""
    return text[-cap:] if len(text) > cap else text


class SubprocessOpenHandsExecutor:
    """Default executor — single subprocess.run call, shell=False, minimal env.

    The executor never invokes git, GitHub, deploy, or merge. It accepts a
    fixed command + args list resolved by the service from server-side
    configuration; request input cannot influence the argv.
    """

    def run(
        self,
        *,
        command: str,
        args: list[str],
        cwd: str,
        timeout_seconds: int,
        max_output_bytes: int,
        working_directory: str | None = None,
        title: str | None = None,
    ) -> OpenHandsExecutionResult:
        # working_directory / title are HTTP-bridge concepts; subprocess
        # executor runs locally with ``cwd`` and ignores them.
        del working_directory, title
        argv = [command, *args]
        env = {"PATH": os.environ.get("PATH", "")}
        per_stream = max(0, max_output_bytes // 2)
        started = time.monotonic()
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            stdout = exc.stdout if isinstance(exc.stdout, str) else (
                exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            )
            stderr = exc.stderr if isinstance(exc.stderr, str) else (
                exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            )
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout=_truncate(stdout or "", per_stream),
                stderr=_truncate(stderr or "", per_stream),
                timed_out=True,
                duration_seconds=duration,
                error=f"timed out after {timeout_seconds}s",
            )
        except (FileNotFoundError, OSError) as exc:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"could not execute OpenHands: {exc}",
            )
        except Exception as exc:  # defensive
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"executor error: {exc}",
            )

        duration = time.monotonic() - started
        return OpenHandsExecutionResult(
            exit_code=int(result.returncode),
            stdout=_truncate(result.stdout or "", per_stream),
            stderr=_truncate(result.stderr or "", per_stream),
            timed_out=False,
            duration_seconds=duration,
            error=None,
        )


class HttpOpenHandsExecutor:
    """Bridge executor: forwards an instruction file to a running upstream
    OpenHands container's HTTP API instead of invoking a CLI subprocess.

    Picked when ``config.OPENHANDS_EXECUTOR=http``. The Protocol surface
    matches :class:`SubprocessOpenHandsExecutor` so the service code is
    unchanged: ``command`` is ignored, the instruction file path is found in
    ``args``, its JSON contents are POSTed as the initial user message to
    ``POST /api/v1/app-conversations``, events are polled until the
    conversation goes quiet, and a synthesized ``OpenHandsExecutionResult``
    is returned. Workspace file mounting between the host and the container
    is a deployment-level concern (set via docker volumes on
    ``openhands-app``) — this executor does not manage mounts.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        poll_interval_seconds: float | None = None,
        quiet_after_seconds: float | None = None,
        http_get=None,
        http_post=None,
    ) -> None:
        from .url_safety import UnsafeURLError, validate_external_base_url

        raw_base = (
            base_url
            if base_url is not None
            else _config.OPENHANDS_HTTP_BASE_URL
        )
        # H9: block the metadata/link-local SSRF class. The bridge is
        # internal-by-design so http is allowed (require_tls_for_public
        # is off) — only dangerous targets are rejected.
        try:
            validate_external_base_url(
                raw_base,
                label="OPENHANDS_HTTP_BASE_URL",
                require_tls_for_public=False,
            )
        except UnsafeURLError as exc:
            raise OpenHandsHttpError(str(exc)) from exc
        self._base_url = raw_base.rstrip("/")
        self._poll_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else _config.OPENHANDS_HTTP_POLL_INTERVAL_SECONDS
        )
        self._quiet_after = (
            quiet_after_seconds
            if quiet_after_seconds is not None
            else _config.OPENHANDS_HTTP_QUIET_AFTER_SECONDS
        )
        # Allow tests to inject stub HTTP callables.
        self._http_get = http_get or _http_get_json
        self._http_post = http_post or _http_post_json

    @staticmethod
    def _find_instruction_path(args: list[str], cwd: str) -> str | None:
        for token in args:
            if not token:
                continue
            if token.endswith(".json") and os.path.exists(token):
                return token
        return None

    def _poll_execution_status(self, conversation_id: str) -> str | None:
        """Best-effort lookup of the upstream conversation's
        ``execution_status``. Returns ``None`` on any failure (network error,
        non-dict response, missing item, missing field) so the caller can
        fall back to the event-count quiet-after heuristic without changing
        prior behavior.
        """
        try:
            resp = self._http_get(
                f"{self._base_url}/api/v1/app-conversations?ids={conversation_id}",
                timeout=10,
            )
        except OpenHandsHttpError:
            return None
        items = resp.get("items") if isinstance(resp, dict) else None
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("id") == conversation_id:
                status = item.get("execution_status")
                return status if isinstance(status, str) else None
        return None

    def run(
        self,
        *,
        command: str,
        args: list[str],
        cwd: str,
        timeout_seconds: int,
        max_output_bytes: int,
        working_directory: str | None = None,
        title: str | None = None,
    ) -> OpenHandsExecutionResult:
        per_stream = max(0, max_output_bytes // 2)
        started = time.monotonic()

        instruction_path = self._find_instruction_path(args, cwd)
        if instruction_path is None:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error="instruction file not found in args",
            )

        try:
            instruction_text = Path(instruction_path).read_text(encoding="utf-8")
        except OSError as exc:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"could not read instruction file: {exc}",
            )

        if working_directory:
            directive = (
                f"Your working directory for this task is `{working_directory}`. "
                "Make all changes inside that directory only. Do not modify "
                "files outside it. Treat that directory as the repository "
                "root for the dev task described below.\n\n---\n\n"
            )
            instruction_text = directive + instruction_text

        payload: dict = {
            "initial_message": {
                "role": "user",
                "content": [{"type": "text", "text": instruction_text}],
                "run": True,
            }
        }
        if title:
            payload["title"] = title

        try:
            created = self._http_post(
                f"{self._base_url}/api/v1/app-conversations",
                payload,
                timeout=min(30, timeout_seconds),
            )
        except OpenHandsHttpError as exc:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr=_truncate(str(exc), per_stream),
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"could not start OpenHands conversation: {exc}",
            )

        start_task_id = created.get("id") if isinstance(created, dict) else None
        if not start_task_id:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr=_truncate(json.dumps(created)[:per_stream], per_stream),
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error="OpenHands did not return a start-task id",
            )

        # The POST returns a start-task id, not the conversation_id. Resolve
        # the actual ``app_conversation_id`` once the start-task is READY.
        conversation_id: str | None = None
        # B3 lever: the start-task -> READY (sandbox/runtime spin-up) phase
        # was hard-capped at 120s regardless of the job timeout. A cold
        # OpenHands runtime routinely needs longer, so DTs silently timed
        # out in resolve and produced ZERO code. The cap is now configurable
        # and defaults high enough for a cold runtime, still bounded by the
        # overall job timeout.
        resolve_cap = float(_config.OPENHANDS_HTTP_RESOLVE_TIMEOUT_SECONDS)
        resolve_deadline = started + min(resolve_cap, max(1, timeout_seconds))
        while True:
            try:
                tasks = self._http_get(
                    f"{self._base_url}/api/v1/app-conversations/start-tasks/search?limit=20",
                    timeout=10,
                )
            except OpenHandsHttpError as exc:
                return OpenHandsExecutionResult(
                    exit_code=None,
                    stdout="",
                    stderr=_truncate(str(exc), per_stream),
                    timed_out=False,
                    duration_seconds=time.monotonic() - started,
                    error=f"could not resolve OpenHands start-task: {exc}",
                )
            for item in (tasks.get("items", []) if isinstance(tasks, dict) else []):
                if isinstance(item, dict) and item.get("id") == start_task_id:
                    conversation_id = item.get("app_conversation_id")
                    if conversation_id and item.get("status") in {"READY", "FAILED"}:
                        break
            if conversation_id:
                break
            if time.monotonic() >= resolve_deadline:
                now = time.monotonic()
                return OpenHandsExecutionResult(
                    exit_code=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    duration_seconds=now - started,
                    # B3: attribute the timeout to the resolve phase so
                    # telemetry shows WHERE it died (was reported as 0.0).
                    resolve_seconds=round(now - started, 3),
                    run_seconds=0.0,
                    error=(
                        "timed out waiting for OpenHands start-task to become "
                        f"READY after {round(now - started)}s "
                        f"(resolve cap {resolve_cap:.0f}s)"
                    ),
                )
            time.sleep(self._poll_interval)

        # H9: the conversation_id came from the bridge's own response and
        # is about to be interpolated into follow-up request URLs. A
        # hostile/compromised bridge returning a crafted id (path/query
        # injection) must not reshape those requests — pin it to a safe
        # id charset. Surface as a normal result (bridge convention), not
        # a raised exception.
        try:
            conversation_id = _safe_oh_id(conversation_id)
        except OpenHandsHttpError as exc:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=str(exc),
            )

        # End of the sandbox/runtime spin-up phase: the conversation is
        # resolved and READY. Everything after this is agent-run time.
        resolve_end = time.monotonic()

        # Poll events until either (a) the upstream conversation reports a
        # terminal execution_status, or (b) the event count stabilizes for
        # ``quiet_after`` seconds, or (c) the overall deadline expires.
        # The execution_status signal is the primary exit condition; the
        # quiet-after heuristic remains as a fallback so older OpenHands
        # builds that don't populate the status field still work.
        events_url = f"{self._base_url}/api/v1/conversation/{conversation_id}/events/search?limit=100"
        count_url = f"{self._base_url}/api/v1/conversation/{conversation_id}/events/count"
        last_count = -1
        last_change = time.monotonic()
        timed_out = False
        deadline = started + max(1, timeout_seconds)
        while True:
            try:
                count_resp = self._http_get(count_url, timeout=10)
            except OpenHandsHttpError as exc:
                return OpenHandsExecutionResult(
                    exit_code=None,
                    stdout="",
                    stderr=_truncate(str(exc), per_stream),
                    timed_out=False,
                    duration_seconds=time.monotonic() - started,
                    error=f"could not poll OpenHands events: {exc}",
                )
            count = _coerce_int(count_resp)
            now = time.monotonic()
            if count != last_count:
                last_count = count
                last_change = now

            status = self._poll_execution_status(conversation_id)
            if status in _TERMINAL_EXECUTION_STATUSES:
                break

            if last_count > 0 and (now - last_change) >= self._quiet_after:
                break
            if now >= deadline:
                timed_out = True
                break
            time.sleep(self._poll_interval)

        # Pull the final events to synthesize stdout/stderr.
        try:
            events_resp = self._http_get(events_url, timeout=15)
        except OpenHandsHttpError as exc:
            return OpenHandsExecutionResult(
                exit_code=None if timed_out else 1,
                stdout="",
                stderr=_truncate(str(exc), per_stream),
                timed_out=timed_out,
                duration_seconds=time.monotonic() - started,
                error=f"could not fetch OpenHands events: {exc}",
            )

        events = events_resp.get("items", []) if isinstance(events_resp, dict) else []
        agent_text, error_text = _summarize_events(events)
        duration = time.monotonic() - started
        resolve_seconds = round(resolve_end - started, 3)
        run_seconds = round(time.monotonic() - resolve_end, 3)

        if timed_out:
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout=_truncate(agent_text, per_stream),
                stderr=_truncate(error_text or "", per_stream),
                timed_out=True,
                duration_seconds=duration,
                resolve_seconds=resolve_seconds,
                run_seconds=run_seconds,
                error=f"timed out after {timeout_seconds}s",
            )

        # Synthesize exit code: a conversation that ended without any error
        # events is treated as success, even if the agent finished silently
        # via tool actions (file edits, bash) and emitted no final text.
        # ForgeLoop's workspace-snapshot diff is the authoritative source of
        # "did the agent change anything" — we should not contradict it just
        # because the agent didn't send a closing chat message.
        exit_code = 1 if error_text else 0
        return OpenHandsExecutionResult(
            exit_code=exit_code,
            stdout=_truncate(agent_text, per_stream),
            stderr=_truncate(error_text or "", per_stream),
            timed_out=False,
            duration_seconds=duration,
            resolve_seconds=resolve_seconds,
            run_seconds=run_seconds,
            error=None,
        )


class OpenHandsHttpError(Exception):
    """Raised by the HTTP helpers for any network/HTTP failure."""


_OH_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def _safe_oh_id(value) -> str:
    """H9: validate a bridge-supplied id before it is interpolated into a
    request URL. Rejects path/query injection from a hostile bridge."""
    if not isinstance(value, str) or not _OH_ID_RE.match(value):
        raise OpenHandsHttpError(
            "OpenHands returned an unsafe conversation/start-task id"
        )
    return value


def _http_post_json(url: str, body: dict, *, timeout: float) -> dict:
    """Default HTTP POST helper used by HttpOpenHandsExecutor.

    Stdlib-only; tests inject a stub instead of mocking urllib.
    """
    import urllib.error
    import urllib.request

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cap = int(_config.OPENHANDS_HTTP_MAX_RESPONSE_BYTES)
            raw = resp.read(cap + 1)
            if len(raw) > cap:
                raise OpenHandsHttpError(
                    f"response from {url} exceeded size cap"
                )
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise OpenHandsHttpError(f"HTTP {exc.code} from {url}: {body_text[:200]}") from exc
    except urllib.error.URLError as exc:
        raise OpenHandsHttpError(f"could not reach {url}: {exc.reason}") from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise OpenHandsHttpError(f"bad response from {url}: {exc}") from exc


def _http_get_json(url: str, *, timeout: float):
    """Default HTTP GET helper; returns parsed JSON or raw int for count endpoints."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cap = int(_config.OPENHANDS_HTTP_MAX_RESPONSE_BYTES)
            raw = resp.read(cap + 1)
            if len(raw) > cap:
                raise OpenHandsHttpError(
                    f"response from {url} exceeded size cap"
                )
            text = raw.decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise OpenHandsHttpError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise OpenHandsHttpError(f"could not reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenHandsHttpError(f"timeout fetching {url}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # /events/count returns a bare integer
        try:
            return int(text.strip())
        except ValueError:
            raise OpenHandsHttpError(f"unexpected response from {url}: {text[:200]}")


def _coerce_int(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    if isinstance(value, dict):
        for k in ("count", "total"):
            if k in value:
                return _coerce_int(value[k])
    return 0


def _summarize_events(events: list) -> tuple[str, str]:
    """Extract agent reply text and any error text from a v1.x event list."""
    agent_chunks: list[str] = []
    error_chunks: list[str] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind") or ev.get("event_type") or ""
        source = ev.get("source") or ""
        if "Message" in kind and source == "agent":
            # OpenHands 1.x nests text under ``llm_message.content``;
            # tests/older formats put it at the top-level ``content``.
            blocks = (
                (ev.get("llm_message") or {}).get("content")
                or ev.get("content")
                or []
            )
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str) and text:
                        agent_chunks.append(text)
        # Some event types carry agent error info.
        if "Error" in kind or ev.get("status") in {"error", "failed"}:
            detail = ev.get("error") or ev.get("message") or ev.get("detail") or ""
            if isinstance(detail, dict):
                detail = json.dumps(detail)
            if isinstance(detail, str) and detail:
                error_chunks.append(detail)
    return "\n".join(agent_chunks), "\n".join(error_chunks)


def _build_default_executor() -> OpenHandsExecutor:
    """Pick the executor class from config. Defaults to the subprocess
    executor; ``OPENHANDS_EXECUTOR=http`` selects :class:`HttpOpenHandsExecutor`.
    """
    name = (_config.OPENHANDS_EXECUTOR or "subprocess").lower()
    if name == "http":
        return HttpOpenHandsExecutor()
    return SubprocessOpenHandsExecutor()


# Module-level singleton — tests monkeypatch this to a fake.
EXECUTOR: OpenHandsExecutor = _build_default_executor()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_approval(
    *,
    approval_repo,
    approval_id: str | None,
    project_id: str,
    dev_task_id: str,
    agent_run_id: str | None,
) -> Approval:
    if approval_id is not None:
        appr = approval_repo.get(approval_id)
        if appr is None:
            raise HTTPException(status_code=400, detail="approval_id not found")
        if appr.status != "approved":
            raise HTTPException(status_code=400, detail="approval is not approved")
        if appr.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="approval does not belong to dev task's project",
            )
        if not (
            (appr.target_type == "dev_task" and appr.target_id == dev_task_id)
            or (
                appr.target_type == "task_decomposition"
                and agent_run_id is not None
                and appr.target_id == agent_run_id
            )
        ):
            raise HTTPException(
                status_code=400,
                detail="approval does not match dev task or its task decomposition",
            )
        return appr

    # #45/M2: scope the implicit approval lookup to this project.
    found = approval_repo.find_approved_for_target(
        "dev_task", dev_task_id, project_id)
    if found is None and agent_run_id is not None:
        found = approval_repo.find_approved_for_target(
            "task_decomposition", agent_run_id, project_id)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail="approval required for OpenHands local execution",
        )
    return found


def _resolve_timeout(requested: int | None) -> int:
    cap = max(1, int(_config.OPENHANDS_EXECUTION_HARD_CAP_SECONDS))
    default_timeout = max(1, min(int(_config.OPENHANDS_TIMEOUT_SECONDS), cap))
    if requested is None:
        return default_timeout
    if requested <= 0:
        raise HTTPException(status_code=400, detail="timeout_seconds must be positive")
    return min(int(requested), cap)


def _resolve_args(instruction_file: str) -> list[str]:
    template = _config.OPENHANDS_ALLOWED_ARGS or []
    args: list[str] = []
    for token in template:
        args.append(token.replace("{instruction_file}", instruction_file))
    return args


def _resolve_container_working_directory(host_root: Path) -> str | None:
    """Translate a host workspace path into the equivalent path inside the
    OpenHands sandbox container, based on a configured parent-mount mapping.

    Returns ``None`` when no mapping is configured (so the HTTP bridge sends
    no working-directory directive — preserves prior behavior). Raises
    ``HTTPException`` 400 when the mapping is partially configured or the
    workspace falls outside the host parent mount, so misconfiguration is
    surfaced loudly rather than silently writing to the wrong directory.
    """
    host_parent = (_config.OPENHANDS_HOST_PARENT_MOUNT or "").strip()
    container_parent = (_config.OPENHANDS_CONTAINER_PARENT_MOUNT or "").strip()
    if not host_parent and not container_parent:
        return None
    if not host_parent or not container_parent:
        raise HTTPException(
            status_code=400,
            detail=(
                "OPENHANDS_HOST_PARENT_MOUNT and OPENHANDS_CONTAINER_PARENT_MOUNT "
                "must both be set or both be empty"
            ),
        )
    try:
        host_parent_resolved = Path(host_parent).expanduser().resolve()
        relative = host_root.relative_to(host_parent_resolved)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"workspace path {host_root} is not inside "
                f"OPENHANDS_HOST_PARENT_MOUNT {host_parent}"
            ),
        )
    container_root = Path(container_parent) / relative
    return str(container_root).replace("\\", "/")


def _resolve_repo_match(workspace, dev_task) -> None:
    if not workspace.code_repository_id:
        return
    # If the dev_task is associated with a single project repo, the workflow's
    # resolve_code_repository would have selected it; we cross-check here.
    # We don't fail hard on missing dev_task association — only if both sides
    # are set and disagree.
    expected_repo_id = None
    try:
        from ..repositories_state import code_repo_repo

        project_repos = code_repo_repo.list_by_project(dev_task.project_id)
        if len(project_repos) == 1:
            expected_repo_id = project_repos[0].id
    except Exception:
        expected_repo_id = None
    if expected_repo_id is not None and workspace.code_repository_id != expected_repo_id:
        raise HTTPException(
            status_code=400,
            detail="workspace.code_repository_id does not match dev task's project repository",
        )


def _capped_combined(stdout: str, stderr: str, cap: int) -> str:
    combined = ""
    if stdout:
        combined += "=== stdout ===\n" + stdout
    if stderr:
        if combined:
            combined += "\n"
        combined += "=== stderr ===\n" + stderr
    if cap > 0 and len(combined) > cap:
        combined = combined[: max(0, cap - len(TRUNCATION_MARKER))] + TRUNCATION_MARKER
    return combined


def _git(root: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=timeout,
        shell=False, env={"PATH": os.environ.get("PATH", "")}, check=False,
    )


class SandboxSyncError(RuntimeError):
    pass


def sync_workspace_to_branch_head(ws_root: Path, *, timeout: int = 60) -> str | None:
    """B1: eliminate sandbox state bleed.

    Before the agent runs, force the workspace to exactly the committed
    HEAD of its current branch and drop any untracked bled files. The
    legitimate flow is: ForgeLoop creates the branch (clean) -> execute
    (agent edits) -> ForgeLoop commits. So at execute-start there should
    be NO uncommitted changes; anything present is bleed (a prior run, or
    the OpenHands bind-mount carrying state) and is discarded.

    Guards (never destructive outside the intended case):
    - workspace must be a git repo
    - current branch must start with the configured forgeloop/ prefix and
      must NOT be a protected branch (main/master/develop/production/...)
    Returns the branch name synced, or None if not a git repo (no-op).
    Raises SandboxSyncError if on a protected/unexpected branch.
    """
    if not (ws_root / ".git").exists():
        return None
    head = _git(ws_root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout)
    if head.returncode != 0:
        return None
    branch = head.stdout.strip()
    protected = {b.strip() for b in _config.GIT_PROTECTED_BRANCHES if b.strip()}
    prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
    if branch in protected or branch == "HEAD" or not branch.startswith(prefix):
        raise SandboxSyncError(
            f"refusing pre-execute sync: workspace is on {branch!r}, "
            f"not a {prefix}* dev-task branch"
        )
    # Fixed argv, shell=False. `reset --hard HEAD` reverts tracked-modified
    # bleed; `clean -fd` removes untracked bled source files. NOT `-x`, so
    # gitignored caches/.venv/.forgeloop survive (kept for speed; the
    # instruction file is (re)written immediately after this).
    r1 = _git(ws_root, ["reset", "--hard", "HEAD"], timeout)
    if r1.returncode != 0:
        raise SandboxSyncError(f"git reset --hard failed: {r1.stderr.strip()}")
    r2 = _git(ws_root, ["clean", "-fd"], timeout)
    if r2.returncode != 0:
        raise SandboxSyncError(f"git clean -fd failed: {r2.stderr.strip()}")
    # B1 extension: a migration-stamped local dev DB is *bled state* too.
    # `git clean -fd` (no -x) deliberately keeps gitignored caches for
    # speed, but a stateful SQLite DB stamped by a prior dev-task's
    # migration carries an alembic_version that a later branch (lacking
    # that revision) cannot satisfy -> spurious "alembic upgrade head"
    # QA failures (cross-dev-task DB bleed). These dev DBs are disposable
    # and regenerated by migrations, so remove them here. Bounded to the
    # workspace root + one level; known disposable extensions only.
    try:
        patterns = ("*.db", "*.sqlite", "*.sqlite3", "*.db-journal")
        for base in (ws_root, *[p for p in ws_root.iterdir() if p.is_dir()
                                and not p.name.startswith(".")
                                and p.name not in ("node_modules",)]):
            for pat in patterns:
                for f in base.glob(pat):
                    if f.is_file():
                        f.unlink()
    except OSError:
        pass  # best-effort; never fail the sync on cleanup
    return branch


def _changed_paths_to_summary(
    diff: workspace_snapshot.WorkspaceDiff, limit: int = 1000
) -> list[OpenHandsChangedPath]:
    out: list[OpenHandsChangedPath] = []
    for change in diff.all_changes():
        if len(out) >= limit:
            break
        out.append(OpenHandsChangedPath(path=change.path, change_type=change.change_type))
    return out


@dataclass
class OpenHandsExecutionService:
    workspace_repo: object
    dev_task_repo: object
    project_repo: object
    approval_repo: object
    tool_run_repo: object
    artifact_repo: object
    audit_writer: object
    repo_safety_profile_repo: object

    def execute(
        self,
        dev_task_id: str,
        body: OpenHandsExecuteRequest,
        actor_email: str,
    ) -> OpenHandsExecuteResponse:
        dev_task = self.dev_task_repo.get(dev_task_id)
        if dev_task is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
        project = self.project_repo.get(dev_task.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if body.mode == "dry_run":
            prepared: OpenHandsPrepareResponse = openhands_workflow.prepare_package(
                dev_task_id,
                OpenHandsPreparePackageRequest(
                    tool_runner_definition_id=body.tool_runner_definition_id
                ),
                actor_email,
            )
            return OpenHandsExecuteResponse(
                tool_run=prepared.tool_run,
                instruction_package=prepared.instruction_package,
                execution_summary=OpenHandsExecutionSummary(
                    mode="dry_run",
                    workspace_id=body.workspace_id,
                ),
            )

        if body.mode != "local":
            raise HTTPException(status_code=400, detail="mode must be 'dry_run' or 'local'")

        # ---- local mode ----
        if not _config.OPENHANDS_EXECUTION_ENABLED:
            raise HTTPException(
                status_code=409,
                detail="OPENHANDS_EXECUTION_DISABLED",
            )
        if not _config.OPENHANDS_COMMAND:
            raise HTTPException(
                status_code=409,
                detail="OPENHANDS_COMMAND_NOT_CONFIGURED",
            )

        workspace = self.workspace_repo.get(body.workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if workspace.project_id != project.id:
            raise HTTPException(
                status_code=400,
                detail="Workspace does not belong to dev task's project",
            )
        if workspace.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Workspace is not ready (status={workspace.status})",
            )

        _resolve_repo_match(workspace, dev_task)
        timeout_seconds = _resolve_timeout(body.timeout_seconds)
        max_output_bytes = max(0, int(_config.OPENHANDS_MAX_OUTPUT_BYTES))

        approval = _resolve_approval(
            approval_repo=self.approval_repo,
            approval_id=body.approval_id,
            project_id=project.id,
            dev_task_id=dev_task.id,
            agent_run_id=getattr(dev_task, "agent_run_id", None),
        )

        # Task 90: RunnerRouter is mandatory for real coding execution.
        # The decision is recorded; an approved direct OpenHands call is
        # the documented broad/complex justification (override audited).
        from .runner_router import RunnerRouteRejected, enforce_runner_route

        _runner_approved = getattr(approval, "status", None) == "approved"
        try:
            _runner_decision = enforce_runner_route(
                dev_task, "openhands", approved=_runner_approved
            )
        except RunnerRouteRejected as e:
            raise HTTPException(status_code=409, detail=str(e))
        self.audit_writer.write(
            "runner_route_decided",
            "dev_task",
            dev_task.id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "requested_runner": "openhands",
                "selected_runner": _runner_decision.runner_name,
                "reason": _runner_decision.reason,
                "warnings": _runner_decision.warnings,
            },
        )

        # Build the instruction package via the existing helper (no duplication).
        from ..repositories_state import (
            code_repo_repo,
            epic_repo,
            project_context_repo,
            requirement_repo,
        )
        from ..services.openhands_workflow import resolve_code_repository

        code_repository = resolve_code_repository(project.id, None, None)
        # If the workspace pins a code repository, prefer it.
        if workspace.code_repository_id:
            wc = code_repo_repo.get(workspace.code_repository_id)
            if wc is not None and wc.project_id == project.id:
                code_repository = wc

        safety_profile = (
            self.repo_safety_profile_repo.get_by_repo(code_repository.id)
            if code_repository is not None
            else None
        )
        project_context = project_context_repo.get(project.id)
        requirement_summary: str | None = None
        if dev_task.requirement_id:
            req = requirement_repo.get(dev_task.requirement_id)
            if req is not None:
                requirement_summary = req.problem_statement or req.title
        epic_title: str | None = None
        if dev_task.epic_id:
            epic = epic_repo.get(dev_task.epic_id)
            if epic is not None:
                epic_title = epic.title

        package_dict = build_openhands_instruction_package(
            project=project,
            dev_task=dev_task,
            code_repository=code_repository,
            safety_profile=safety_profile,
            project_context=project_context,
            requirement_summary=requirement_summary,
            epic_title=epic_title,
        )
        package_dict["mode"] = "dry_run"  # schema constraint; execution mode is on ToolRun
        package_dict["instructions"] = list(package_dict.get("instructions") or []) + [
            "Stay inside the workspace root; do not modify files elsewhere.",
            "Do not invoke git, gh, docker, kubectl, terraform, or cloud CLIs.",
            "Required checks are not run automatically by ForgeLoop here — "
            "the operator will trigger them after review.",
        ]
        package_json = json.dumps(package_dict, sort_keys=True)

        # Persist instruction package artifact.
        now = _now()
        pkg_artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=pkg_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="openhands_instruction_package",
            content=package_json,
            created_at=now,
        ))

        # #45/H4: re-assert workspace safety before B1 hard-sync /
        # reset --hard can touch the host filesystem.
        from .workspace_paths import (
            WorkspacePathError,
            assert_workspace_safe,
        )

        try:
            ws_root = assert_workspace_safe(workspace.root_path)
        except WorkspacePathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # B1: hard-sync the workspace to its branch HEAD before the agent
        # runs, so no bled state (prior run / bind-mount carryover) leaks
        # into this dev_task's output. Local mode only; guarded to
        # forgeloop/* non-protected branches.
        try:
            synced_branch = sync_workspace_to_branch_head(
                ws_root, timeout=int(_config.GIT_TIMEOUT_SECONDS)
            )
        except SandboxSyncError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        if synced_branch:
            self.audit_writer.write(
                "openhands_workspace_synced",
                "workspace",
                workspace.id,
                project_id=project.id,
                actor_email=actor_email,
                details={"branch": synced_branch, "dev_task_id": dev_task.id},
            )

        # Write the instruction file into a ForgeLoop-controlled metadata dir
        # under the workspace root.
        meta_dir = ws_root / ".forgeloop" / "openhands"
        try:
            meta_dir.mkdir(parents=True, exist_ok=True)
            instruction_path = meta_dir / f"{pkg_artifact_id}.json"
            instruction_path.write_text(package_json, encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"could not write instruction file inside workspace: {exc}",
            )

        # Snapshot before.
        blocked_paths = list(safety_profile.blocked_paths) if safety_profile else []
        snap_before = workspace_snapshot.snapshot(ws_root, blocked_paths=blocked_paths)

        # Build ToolRun in running state.
        run_id = str(uuid.uuid4())
        running = ToolRun(
            id=run_id,
            project_id=project.id,
            code_repository_id=code_repository.id if code_repository is not None else None,
            tool_runner_definition_id=body.tool_runner_definition_id,
            target_type="dev_task",
            target_id=dev_task.id,
            runner_type="openhands",
            mode="local",
            status="running",
            conclusion=None,
            summary="OpenHands local execution started",
            output=None,
            artifact_id=pkg_artifact_id,
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.tool_run_repo.save(running)

        self.audit_writer.write(
            "openhands_execution_requested",
            "tool_run",
            run_id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "dev_task_id": dev_task.id,
                "workspace_id": workspace.id,
                "approval_id": approval.id,
                "mode": "local",
                "code_repository_id": code_repository.id if code_repository else None,
            },
        )
        self.audit_writer.write(
            "openhands_execution_started",
            "tool_run",
            run_id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "timeout_seconds": timeout_seconds,
            },
        )

        # Resolve args (server-side template — request cannot influence argv).
        args = _resolve_args(str(instruction_path))

        # Map host workspace path to in-container path for the HTTP bridge
        # (no-op for subprocess executor). Misconfiguration raises 400 here.
        container_working_directory = _resolve_container_working_directory(ws_root)

        # Invoke executor.
        result = EXECUTOR.run(
            command=_config.OPENHANDS_COMMAND,
            args=args,
            cwd=str(ws_root),
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            working_directory=container_working_directory,
            title=dev_task.title,
        )

        # Snapshot after.
        snap_after = workspace_snapshot.snapshot(ws_root, blocked_paths=blocked_paths)
        wdiff = workspace_snapshot.diff(snap_before, snap_after, blocked_paths=blocked_paths)
        changed = _changed_paths_to_summary(wdiff)
        blocked_changes = list(wdiff.blocked_path_changes)

        # Build output artifact (capped).
        completed_at = _now()
        output_text = _capped_combined(result.stdout, result.stderr, max_output_bytes)
        output_artifact_id: str | None = None
        if output_text:
            output_artifact_id = str(uuid.uuid4())
            self.artifact_repo.save(_storage.store_artifact(
                artifact_id=output_artifact_id,
                artifact_type="openhands_execution_output",
                content=output_text,
                created_at=completed_at,
                project_id=project.id,
            ))

        # Changed-paths artifact.
        changes_payload = {
            "added": [c.path for c in wdiff.added],
            "modified": [c.path for c in wdiff.modified],
            "deleted": [c.path for c in wdiff.deleted],
            "blocked_path_changes": blocked_changes,
            "snapshot_truncated": snap_before.truncated or snap_after.truncated,
        }
        changes_artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=changes_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="openhands_execution_changed_paths",
            content=json.dumps(changes_payload, sort_keys=True),
            created_at=completed_at,
        ))

        # Map outcome.
        status: ToolRunStatus
        conclusion: ToolRunConclusion
        summary: str
        audit_action: str

        if blocked_changes:
            status = "failed"
            conclusion = "requires_human_action"
            summary = (
                f"Blocked-path changes detected ({len(blocked_changes)}): "
                + ", ".join(blocked_changes[:5])
                + ("…" if len(blocked_changes) > 5 else "")
            )
            audit_action = "openhands_execution_blocked"
        elif result.timed_out:
            status = "failed"
            conclusion = "failure"
            summary = f"TIMED OUT after {timeout_seconds}s"
            audit_action = "openhands_execution_timed_out"
        elif result.error is not None and result.exit_code is None:
            status = "failed"
            conclusion = "failure"
            summary = result.error
            audit_action = "openhands_execution_failed"
        elif result.exit_code == 0:
            status = "completed"
            conclusion = "requires_human_action"
            summary = (
                f"OpenHands exited 0; {len(changed)} changed path(s) — human review required"
            )
            audit_action = "openhands_execution_completed"
        else:
            status = "failed"
            conclusion = "failure"
            summary = f"OpenHands exited with code {result.exit_code}"
            audit_action = "openhands_execution_failed"

        updated = running.model_copy(update={
            "status": status,
            "conclusion": conclusion,
            "summary": summary,
            "output": output_text or None,
            "artifact_id": changes_artifact_id,
            "completed_at": completed_at,
            "updated_at": completed_at,
        })
        self.tool_run_repo.save(updated)

        # C2 follow-up: emit a CostRecord for the execution so the
        # observability provider (Langfuse) traces the sprint path. The
        # OpenHands HTTP bridge does not surface LLM token usage, so token
        # counts are 0 by design — the value here is the phase-timing
        # metadata (B3) and a per-run generation. Never breaks execution.
        try:
            from ..repositories_state import cost_record_repo as _crr
            from .cost_tracking import record_cost as _record_cost

            _record_cost(
                _crr,
                project_id=project.id,
                source_type="tool_run",
                source_id=updated.id,
                workflow_type="coding",
                provider="openhands",
                model=(_config.OPENHANDS_EXECUTOR or "http-bridge"),
                input_tokens=0,
                output_tokens=0,
                metadata={
                    "dev_task_id": updated.target_id,
                    "workspace_id": workspace.id,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_seconds": round(result.duration_seconds, 3),
                    "resolve_seconds": round(result.resolve_seconds, 3),
                    "run_seconds": round(result.run_seconds, 3),
                    "conclusion": conclusion,
                },
            )
        except Exception:
            pass

        self.audit_writer.write(
            audit_action,
            "tool_run",
            updated.id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "changed_paths_count": len(changed),
                "blocked_path_changes_count": len(blocked_changes),
                "duration_seconds": round(result.duration_seconds, 3),
                "resolve_seconds": round(result.resolve_seconds, 3),
                "run_seconds": round(result.run_seconds, 3),
            },
        )

        summary_obj = OpenHandsExecutionSummary(
            mode="local",
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            duration_seconds=round(result.duration_seconds, 3),
            changed_paths=changed,
            blocked_path_changes=blocked_changes,
            stdout_tail=_tail(result.stdout),
            stderr_tail=_tail(result.stderr),
            snapshot_truncated=snap_before.truncated or snap_after.truncated,
            workspace_id=workspace.id,
        )

        return OpenHandsExecuteResponse(
            tool_run=updated,
            instruction_package=OpenHandsInstructionPackage(**package_dict),
            execution_summary=summary_obj,
        )


def _service() -> OpenHandsExecutionService:
    from ..repositories_state import (
        approval_repo,
        artifact_repo,
        audit_writer,
        dev_task_repo,
        project_repo,
        repo_safety_profile_repo,
        tool_run_repo,
        workspace_repo,
    )
    return OpenHandsExecutionService(
        workspace_repo=workspace_repo,
        dev_task_repo=dev_task_repo,
        project_repo=project_repo,
        approval_repo=approval_repo,
        tool_run_repo=tool_run_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
        repo_safety_profile_repo=repo_safety_profile_repo,
    )


def execute(
    dev_task_id: str,
    body: OpenHandsExecuteRequest,
    actor_email: str,
) -> OpenHandsExecuteResponse:
    # Concurrency hardening: a same-workspace execution must not overlap
    # (B1 hard-sync would corrupt a concurrent run). Task 91 also blocks
    # the same dev task running concurrently across different workspaces.
    # Both locks are non-blocking and release on success/failure/timeout.
    from .workspace_locks import (
        TaskBusyError,
        WorkspaceBusyError,
        task_execution_lock,
        workspace_execution_lock,
    )

    ws_id = getattr(body, "workspace_id", None)
    if getattr(body, "mode", None) != "local" or not ws_id:
        return _service().execute(dev_task_id, body, actor_email)
    try:
        with task_execution_lock(dev_task_id):
            with workspace_execution_lock(ws_id):
                from .cache_provider import runner_dedupe_touch

                runner_dedupe_touch(dev_task_id, ws_id)
                _t0 = time.perf_counter()
                try:
                    return _service().execute(
                        dev_task_id, body, actor_email
                    )
                finally:
                    try:  # Task 96 metric (no-op if disabled)
                        from .metrics import observe_runner_duration

                        observe_runner_duration(
                            time.perf_counter() - _t0, "openhands"
                        )
                    except Exception:
                        pass
    except TaskBusyError as exc:
        raise HTTPException(status_code=409, detail="TASK_BUSY") from exc
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail="WORKSPACE_BUSY") from exc


__all__ = [
    "EXECUTOR",
    "HttpOpenHandsExecutor",
    "OpenHandsExecutionResult",
    "OpenHandsExecutionService",
    "OpenHandsExecutor",
    "OpenHandsHttpError",
    "SubprocessOpenHandsExecutor",
    "execute",
]
