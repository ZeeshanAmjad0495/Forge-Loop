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


class OpenHandsExecutionResult(BaseModel):
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
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
    ) -> OpenHandsExecutionResult:
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


# Module-level singleton — tests monkeypatch this to a fake.
EXECUTOR: OpenHandsExecutor = SubprocessOpenHandsExecutor()


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

    found = approval_repo.find_approved_for_target("dev_task", dev_task_id)
    if found is None and agent_run_id is not None:
        found = approval_repo.find_approved_for_target("task_decomposition", agent_run_id)
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

        # Write the instruction file into a ForgeLoop-controlled metadata dir
        # under the workspace root.
        ws_root = Path(workspace.root_path).resolve()
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

        # Invoke executor.
        result = EXECUTOR.run(
            command=_config.OPENHANDS_COMMAND,
            args=args,
            cwd=str(ws_root),
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
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
    return _service().execute(dev_task_id, body, actor_email)


__all__ = [
    "EXECUTOR",
    "OpenHandsExecutionResult",
    "OpenHandsExecutionService",
    "OpenHandsExecutor",
    "SubprocessOpenHandsExecutor",
    "execute",
]
