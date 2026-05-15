"""C1 follow-up: real Aider execution bridge.

Makes Aider a true coding runner (not package-only). Mirrors the OpenHands
local-execution security model exactly and reuses its proven machinery:

- Server-controlled argv only — request input can NEVER influence the
  command line (no injection surface).
- ``shell=False``, minimal env (PATH + the Ollama base URL), ``cwd`` pinned
  to the workspace root, timeout + output cap.
- B1 hard-sync before the run (no bled state), blocked-path snapshot diff,
  approval gate, audit trail, CostRecord -> Langfuse.
- Aider runs non-interactively against the local Ollama; it never commits
  (``--no-auto-commits``), never pushes, never touches GitHub. ForgeLoop
  owns the branch/commit/PR lifecycle.

Gated by ``AIDER_EXECUTION_ENABLED``; a misroute can never shell out.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from .. import config as _config
from ..models import Artifact, ToolRun, ToolRunConclusion, ToolRunStatus
from ..tool_runners.aider import build_aider_instruction_package
from . import artifact_storage as _storage
from . import workspace_snapshot
from .openhands_execution import (
    OpenHandsExecutionResult,
    SandboxSyncError,
    _capped_combined,
    _changed_paths_to_summary,
    _now,
    _resolve_approval,
    _resolve_repo_match,
    _truncate,
    sync_workspace_to_branch_head,
)


def _resolve_timeout(requested: int | None) -> int:
    cap = max(1, int(_config.AIDER_EXECUTION_HARD_CAP_SECONDS))
    default_timeout = max(1, min(int(_config.AIDER_TIMEOUT_SECONDS), cap))
    if requested is None:
        return default_timeout
    if int(requested) <= 0:
        raise HTTPException(
            status_code=400, detail="timeout_seconds must be positive"
        )
    return min(int(requested), cap)


def _resolve_model() -> str:
    """Server-side model id. Aider+Ollama uses the ``ollama/<model>`` form."""
    provider = _config.AIDER_LLM_PROVIDER or _config.LLM_PROVIDER
    if provider == "ollama":
        model = _config.AIDER_MODEL or _config.OLLAMA_DEFAULT_MODEL
        return f"ollama/{model}"
    return _config.AIDER_MODEL or _config.LLM_MODEL or "ollama/qwen2.5-coder:3b"


def _build_argv(message_file: str) -> list[str]:
    """Fixed, server-controlled argv. The dev-task instruction is passed via
    ``--message-file`` (file content, never argv) so there is no argv
    injection surface. No file list — Aider edits the repo as needed."""
    return [
        _config.AIDER_COMMAND,
        "--model", _resolve_model(),
        "--message-file", message_file,
        "--yes-always",
        "--no-auto-commits",
        "--no-stream",
        "--no-check-update",
        "--no-gitignore",
        "--map-tokens", "0",
    ]


class AiderSubprocessExecutor:
    """Single ``subprocess.run`` — shell=False, minimal env. Mirrors
    SubprocessOpenHandsExecutor; adds only ``OLLAMA_API_BASE`` so Aider can
    reach the local model. argv is fixed by the service."""

    def run(
        self,
        *,
        argv: list[str],
        cwd: str,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> OpenHandsExecutionResult:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "OLLAMA_API_BASE": _config.OLLAMA_BASE_URL or "",
            "HOME": os.environ.get("HOME", ""),
            "AIDER_ANALYTICS": "false",
        }
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
            stdout = exc.stdout if isinstance(exc.stdout, str) else (
                exc.stdout.decode("utf-8", errors="replace")
                if exc.stdout else ""
            )
            stderr = exc.stderr if isinstance(exc.stderr, str) else (
                exc.stderr.decode("utf-8", errors="replace")
                if exc.stderr else ""
            )
            return OpenHandsExecutionResult(
                exit_code=None,
                stdout=_truncate(stdout or "", per_stream),
                stderr=_truncate(stderr or "", per_stream),
                timed_out=True,
                duration_seconds=time.monotonic() - started,
                error=f"timed out after {timeout_seconds}s",
            )
        except (FileNotFoundError, OSError) as exc:
            return OpenHandsExecutionResult(
                exit_code=None, stdout="", stderr="", timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"could not execute Aider: {exc}",
            )
        except Exception as exc:  # defensive
            return OpenHandsExecutionResult(
                exit_code=None, stdout="", stderr="", timed_out=False,
                duration_seconds=time.monotonic() - started,
                error=f"executor error: {exc}",
            )
        return OpenHandsExecutionResult(
            exit_code=int(result.returncode),
            stdout=_truncate(result.stdout or "", per_stream),
            stderr=_truncate(result.stderr or "", per_stream),
            timed_out=False,
            duration_seconds=time.monotonic() - started,
            error=None,
        )


EXECUTOR = AiderSubprocessExecutor()


@dataclass
class AiderExecutionService:
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
        body,
        actor_email: str,
    ) -> ToolRun:
        dev_task = self.dev_task_repo.get(dev_task_id)
        if dev_task is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
        project = self.project_repo.get(dev_task.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        if body.mode != "local":
            raise HTTPException(
                status_code=400,
                detail="aider execute supports mode='local' only",
            )
        if not _config.AIDER_EXECUTION_ENABLED:
            raise HTTPException(status_code=409, detail="AIDER_EXECUTION_DISABLED")

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
        max_output_bytes = max(0, int(_config.AIDER_MAX_OUTPUT_BYTES))

        approval = _resolve_approval(
            approval_repo=self.approval_repo,
            approval_id=body.approval_id,
            project_id=project.id,
            dev_task_id=dev_task.id,
            agent_run_id=getattr(dev_task, "agent_run_id", None),
        )

        from ..repositories_state import (
            code_repo_repo,
            epic_repo,
            project_context_repo,
            requirement_repo,
        )
        from .openhands_workflow import resolve_code_repository

        code_repository = resolve_code_repository(project.id, None, None)
        if workspace.code_repository_id:
            wc = code_repo_repo.get(workspace.code_repository_id)
            if wc is not None and wc.project_id == project.id:
                code_repository = wc
        safety_profile = (
            self.repo_safety_profile_repo.get_by_repo(code_repository.id)
            if code_repository is not None else None
        )
        project_context = project_context_repo.get(project.id)
        requirement_summary = None
        if dev_task.requirement_id:
            req = requirement_repo.get(dev_task.requirement_id)
            if req is not None:
                requirement_summary = req.problem_statement or req.title
        epic_title = None
        if dev_task.epic_id:
            epic = epic_repo.get(dev_task.epic_id)
            if epic is not None:
                epic_title = epic.title

        package = build_aider_instruction_package(
            project=project,
            dev_task=dev_task,
            code_repository=code_repository,
            safety_profile=safety_profile,
            project_context=project_context,
            requirement_summary=requirement_summary,
            epic_title=epic_title,
        )
        # Aider consumes a free-text message, not JSON. Render a compact,
        # instruction-first prompt; keep the JSON too for audit parity.
        prompt = _render_prompt(package, dev_task)
        package_json = json.dumps(package, sort_keys=True)
        now = _now()
        pkg_artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=pkg_artifact_id, ticket_id=None, requirement_id=None,
            agent_run_id=None, artifact_type="aider_instruction_package",
            content=package_json, created_at=now,
        ))

        ws_root = Path(workspace.root_path).resolve()
        try:
            synced_branch = sync_workspace_to_branch_head(
                ws_root, timeout=int(_config.GIT_TIMEOUT_SECONDS)
            )
        except SandboxSyncError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        if synced_branch:
            self.audit_writer.write(
                "aider_workspace_synced", "workspace", workspace.id,
                project_id=project.id, actor_email=actor_email,
                details={"branch": synced_branch, "dev_task_id": dev_task.id},
            )

        meta_dir = ws_root / ".forgeloop" / "aider"
        try:
            meta_dir.mkdir(parents=True, exist_ok=True)
            message_path = meta_dir / f"{pkg_artifact_id}.md"
            message_path.write_text(prompt, encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"could not write Aider message file: {exc}",
            )

        blocked_paths = list(safety_profile.blocked_paths) if safety_profile else []
        snap_before = workspace_snapshot.snapshot(
            ws_root, blocked_paths=blocked_paths
        )

        run_id = str(uuid.uuid4())
        running = ToolRun(
            id=run_id, project_id=project.id,
            code_repository_id=code_repository.id if code_repository else None,
            tool_runner_definition_id=body.tool_runner_definition_id,
            target_type="dev_task", target_id=dev_task.id,
            runner_type="aider", mode="local", status="running",
            conclusion=None, summary="Aider local execution started",
            output=None, artifact_id=pkg_artifact_id,
            started_at=now, completed_at=None, created_at=now, updated_at=now,
        )
        self.tool_run_repo.save(running)
        self.audit_writer.write(
            "aider_execution_requested", "tool_run", run_id,
            project_id=project.id, actor_email=actor_email,
            details={
                "dev_task_id": dev_task.id, "workspace_id": workspace.id,
                "approval_id": approval.id, "mode": "local",
            },
        )
        self.audit_writer.write(
            "aider_execution_started", "tool_run", run_id,
            project_id=project.id, actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "timeout_seconds": timeout_seconds,
            },
        )

        argv = _build_argv(str(message_path))
        result = EXECUTOR.run(
            argv=argv, cwd=str(ws_root),
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )

        snap_after = workspace_snapshot.snapshot(
            ws_root, blocked_paths=blocked_paths
        )
        wdiff = workspace_snapshot.diff(
            snap_before, snap_after, blocked_paths=blocked_paths
        )
        changed = _changed_paths_to_summary(wdiff)
        blocked_changes = list(wdiff.blocked_path_changes)

        completed_at = _now()
        output_text = _capped_combined(
            result.stdout, result.stderr, max_output_bytes
        )
        if output_text:
            oid = str(uuid.uuid4())
            self.artifact_repo.save(_storage.store_artifact(
                artifact_id=oid, artifact_type="aider_execution_output",
                content=output_text, created_at=completed_at,
                project_id=project.id,
            ))

        changes_artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=changes_artifact_id, ticket_id=None, requirement_id=None,
            agent_run_id=None,
            artifact_type="aider_execution_changed_paths",
            content=json.dumps({
                "added": [c.path for c in wdiff.added],
                "modified": [c.path for c in wdiff.modified],
                "deleted": [c.path for c in wdiff.deleted],
                "blocked_path_changes": blocked_changes,
                "snapshot_truncated": snap_before.truncated
                or snap_after.truncated,
            }, sort_keys=True),
            created_at=completed_at,
        ))

        status: ToolRunStatus
        conclusion: ToolRunConclusion
        if blocked_changes:
            status, conclusion = "failed", "requires_human_action"
            summary = (
                f"Blocked-path changes ({len(blocked_changes)}): "
                + ", ".join(blocked_changes[:5])
            )
            audit_action = "aider_execution_blocked"
        elif result.timed_out:
            status, conclusion = "failed", "failure"
            summary = f"TIMED OUT after {timeout_seconds}s"
            audit_action = "aider_execution_timed_out"
        elif result.error is not None and result.exit_code is None:
            status, conclusion = "failed", "failure"
            summary = result.error
            audit_action = "aider_execution_failed"
        elif result.exit_code == 0:
            status, conclusion = "completed", "requires_human_action"
            summary = (
                f"Aider exited 0; {len(changed)} changed path(s) — "
                "human review required"
            )
            audit_action = "aider_execution_completed"
        else:
            status, conclusion = "failed", "failure"
            summary = f"Aider exited with code {result.exit_code}"
            audit_action = "aider_execution_failed"

        updated = running.model_copy(update={
            "status": status, "conclusion": conclusion, "summary": summary,
            "output": output_text or None,
            "artifact_id": changes_artifact_id,
            "completed_at": completed_at, "updated_at": completed_at,
        })
        self.tool_run_repo.save(updated)

        # Cost record -> Langfuse (parity with OpenHands; Aider via Ollama
        # exposes no token usage, so counts are 0 — value is the metadata).
        try:
            from ..repositories_state import cost_record_repo as _crr
            from .cost_tracking import record_cost as _record_cost
            _record_cost(
                _crr, project_id=project.id, source_type="tool_run",
                source_id=updated.id, workflow_type="coding",
                provider="aider", model=_resolve_model(),
                input_tokens=0, output_tokens=0,
                metadata={
                    "dev_task_id": dev_task.id,
                    "workspace_id": workspace.id,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "duration_seconds": round(result.duration_seconds, 3),
                    "conclusion": conclusion,
                },
            )
        except Exception:
            pass

        self.audit_writer.write(
            audit_action, "tool_run", updated.id,
            project_id=project.id, actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "changed_paths_count": len(changed),
                "blocked_path_changes_count": len(blocked_changes),
                "duration_seconds": round(result.duration_seconds, 3),
            },
        )
        return updated


def _render_prompt(package: dict, dev_task) -> str:
    dt = package.get("dev_task", {})
    lines = [
        f"# Task: {dt.get('title') or dev_task.title}",
        "",
        dt.get("description") or "",
        "",
        "## Acceptance criteria",
    ]
    lines += [f"- {a}" for a in (dt.get("acceptance_criteria") or [])]
    lines += ["", "## Rules"]
    lines += [f"- {i}" for i in (package.get("instructions") or [])]
    ctx = package.get("context", {})
    if ctx.get("requirement_summary"):
        lines += ["", "## Requirement", ctx["requirement_summary"]]
    return "\n".join(lines).strip() + "\n"


def _service() -> AiderExecutionService:
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
    return AiderExecutionService(
        workspace_repo=workspace_repo,
        dev_task_repo=dev_task_repo,
        project_repo=project_repo,
        approval_repo=approval_repo,
        tool_run_repo=tool_run_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
        repo_safety_profile_repo=repo_safety_profile_repo,
    )


def execute(dev_task_id: str, body, actor_email: str) -> ToolRun:
    # Same per-workspace mutual exclusion as the OpenHands path: a
    # concurrent same-workspace run would be corrupted by B1 hard-sync.
    from .workspace_locks import WorkspaceBusyError, workspace_execution_lock

    ws_id = getattr(body, "workspace_id", None)
    if not ws_id:
        return _service().execute(dev_task_id, body, actor_email)
    try:
        with workspace_execution_lock(ws_id):
            return _service().execute(dev_task_id, body, actor_email)
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail="WORKSPACE_BUSY") from exc


__all__ = ["AiderExecutionService", "AiderSubprocessExecutor", "execute"]
