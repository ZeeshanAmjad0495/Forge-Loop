"""Safe, workspace-scoped command runner.

Workspace-scoped, allowlist-based, non-shell. Never uses shell=True. Never
inherits process environment beyond PATH. Enforces timeout, output size cap,
and audit trail.

Routes call this service; this service calls repository abstractions and the
workspace_paths helper. No Firestore, no GitHub, no network, no LLM.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .. import config
from ..models import (
    Artifact,
    CommandDefinition,
    CommandDefinitionCreate,
    CommandDefinitionUpdate,
    CommandRun,
    CommandRunCreate,
)


TRUNCATION_MARKER = "\n...[truncated]"


class CommandRunnerDisabled(RuntimeError):
    pass


class CommandDefinitionNotFound(LookupError):
    pass


class CommandRunNotFound(LookupError):
    pass


class WorkspaceNotFoundError(LookupError):
    pass


class ProjectNotFoundError(LookupError):
    pass


class CodeRepositoryNotFoundError(LookupError):
    pass


class WorkspaceNotReady(ValueError):
    pass


class CommandValidationError(ValueError):
    pass


class CommandBlocked(ValueError):
    """Raised internally when validation produces a blocked run record."""


def validate_command_executable(command: str) -> None:
    allowed = config.COMMAND_RUNNER_ALLOWED_COMMANDS
    blocked = config.COMMAND_RUNNER_BLOCKED_COMMANDS
    if command in blocked:
        raise CommandBlocked(f"command {command!r} is blocked")
    if allowed and command not in allowed:
        raise CommandBlocked(f"command {command!r} is not on the allowlist")


def resolve_cwd(workspace_root: str, working_directory: str | None) -> Path:
    root = Path(workspace_root).resolve(strict=True)
    if working_directory:
        candidate = (root / working_directory).resolve(strict=True)
    else:
        candidate = root
    if not candidate.is_dir():
        raise CommandValidationError("working_directory must be an existing directory")
    if not (candidate == root or candidate.is_relative_to(root)):
        raise CommandValidationError("working_directory must be inside workspace root")
    return candidate


def _truncate(text: str, cap: int) -> str:
    if cap <= 0:
        return ""
    if len(text) <= cap:
        return text
    head = text[: max(0, cap - len(TRUNCATION_MARKER))]
    return head + TRUNCATION_MARKER


@dataclass
class CommandRunnerService:
    command_def_repo: object
    command_run_repo: object
    project_repo: object
    workspace_repo: object
    code_repo_repo: object
    artifact_repo: object
    audit_writer: object

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_project(self, project_id: str) -> None:
        if self.project_repo.get(project_id) is None:
            raise ProjectNotFoundError(project_id)

    def _require_workspace_for_project(self, project_id: str, workspace_id: str):
        w = self.workspace_repo.get(workspace_id)
        if w is None or w.project_id != project_id:
            raise WorkspaceNotFoundError(workspace_id)
        return w

    def _require_code_repository(self, project_id: str, code_repository_id: str) -> None:
        r = self.code_repo_repo.get(code_repository_id)
        if r is None or r.project_id != project_id:
            raise CodeRepositoryNotFoundError(code_repository_id)

    # ---------- CommandDefinition ----------

    def create_definition(
        self,
        project_id: str,
        body: CommandDefinitionCreate,
        *,
        actor_email: str | None,
    ) -> CommandDefinition:
        self._require_project(project_id)
        if body.workspace_id is not None:
            self._require_workspace_for_project(project_id, body.workspace_id)
        if body.code_repository_id is not None:
            self._require_code_repository(project_id, body.code_repository_id)

        try:
            validate_command_executable(body.command)
        except CommandBlocked as exc:
            raise CommandValidationError(str(exc)) from exc

        timeout = min(body.timeout_seconds, config.COMMAND_RUNNER_MAX_TIMEOUT_SECONDS)

        now = self._now()
        definition = CommandDefinition(
            id=str(uuid.uuid4()),
            project_id=project_id,
            workspace_id=body.workspace_id,
            code_repository_id=body.code_repository_id,
            name=body.name,
            command=body.command,
            args=list(body.args),
            command_type=body.command_type,
            enabled=body.enabled,
            requires_approval=body.requires_approval,
            timeout_seconds=timeout,
            working_directory=body.working_directory,
            description=body.description,
            created_at=now,
            updated_at=now,
        )
        self.command_def_repo.save(definition)
        self.audit_writer.write(
            "command_definition_created",
            "command_definition",
            definition.id,
            project_id=project_id,
            actor_email=actor_email,
            details={
                "command": definition.command,
                "command_type": definition.command_type,
                "workspace_id": definition.workspace_id,
                "enabled": definition.enabled,
            },
        )
        return definition

    def list_definitions_by_project(self, project_id: str) -> list[CommandDefinition]:
        self._require_project(project_id)
        return self.command_def_repo.list_by_project(project_id)

    def get_definition(self, definition_id: str) -> CommandDefinition:
        d = self.command_def_repo.get(definition_id)
        if d is None:
            raise CommandDefinitionNotFound(definition_id)
        return d

    def update_definition(
        self,
        definition_id: str,
        body: CommandDefinitionUpdate,
        *,
        actor_email: str | None,
    ) -> CommandDefinition:
        definition = self.get_definition(definition_id)
        updates = body.model_dump(exclude_unset=True)

        if "command" in updates and updates["command"] is not None:
            try:
                validate_command_executable(updates["command"])
            except CommandBlocked as exc:
                raise CommandValidationError(str(exc)) from exc

        if "timeout_seconds" in updates and updates["timeout_seconds"] is not None:
            updates["timeout_seconds"] = min(
                updates["timeout_seconds"], config.COMMAND_RUNNER_MAX_TIMEOUT_SECONDS
            )

        updates["updated_at"] = self._now()
        updated = definition.model_copy(update=updates)
        self.command_def_repo.update(updated)
        self.audit_writer.write(
            "command_definition_updated",
            "command_definition",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={"changed_fields": [k for k in updates.keys() if k != "updated_at"]},
        )
        return updated

    # ---------- CommandRun ----------

    def run(
        self,
        workspace_id: str,
        body: CommandRunCreate,
        *,
        actor_email: str | None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> CommandRun:
        if not config.COMMAND_RUNNER_ENABLED:
            raise CommandRunnerDisabled("command runner is disabled")

        workspace = self.workspace_repo.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(workspace_id)

        # Resolve command spec from definition or ad-hoc
        definition: CommandDefinition | None = None
        if body.command_definition_id:
            definition = self.command_def_repo.get(body.command_definition_id)
            if definition is None:
                raise CommandDefinitionNotFound(body.command_definition_id)
            if definition.project_id != workspace.project_id:
                raise CommandDefinitionNotFound(body.command_definition_id)
            if not definition.enabled:
                raise CommandValidationError("command definition is disabled")
            if (
                definition.workspace_id is not None
                and definition.workspace_id != workspace.id
            ):
                raise CommandValidationError(
                    "command definition is bound to a different workspace"
                )
            command = definition.command
            args = list(definition.args)
            timeout_seconds = (
                body.timeout_seconds
                if body.timeout_seconds is not None
                else definition.timeout_seconds
            )
            working_directory = (
                body.working_directory
                if body.working_directory is not None
                else definition.working_directory
            )
        else:
            if not body.command:
                raise CommandValidationError(
                    "command_definition_id or command is required"
                )
            command = body.command
            args = list(body.args or [])
            timeout_seconds = body.timeout_seconds or 60
            working_directory = body.working_directory

        timeout_seconds = max(1, min(timeout_seconds, config.COMMAND_RUNNER_MAX_TIMEOUT_SECONDS))

        # Build pending run skeleton — saved in every terminal path.
        now = self._now()
        run = CommandRun(
            id=str(uuid.uuid4()),
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            command_definition_id=definition.id if definition else None,
            target_type=body.target_type,
            target_id=body.target_id,
            command=command,
            args=args,
            status="pending",
            conclusion=None,
            exit_code=None,
            stdout=None,
            stderr=None,
            output_summary=None,
            artifact_id=None,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
            error_message=None,
        )
        self.command_run_repo.save(run)
        self.audit_writer.write(
            "command_run_requested",
            "command_run",
            run.id,
            project_id=run.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": run.workspace_id,
                "command": run.command,
                "args": run.args,
                "command_definition_id": run.command_definition_id,
            },
        )

        # Workspace readiness check (block if not ready/registered)
        if workspace.status not in ("ready", "registered"):
            return self._record_blocked(
                run, actor_email, f"workspace status is {workspace.status!r}"
            )

        # Allow/block validation
        try:
            validate_command_executable(command)
        except CommandBlocked as exc:
            return self._record_blocked(run, actor_email, str(exc))

        # cwd resolution
        try:
            cwd = resolve_cwd(workspace.root_path, working_directory)
        except (FileNotFoundError, OSError) as exc:
            return self._record_blocked(
                run, actor_email, f"could not resolve working_directory: {exc}"
            )
        except CommandValidationError as exc:
            return self._record_blocked(run, actor_email, str(exc))

        # Mark running, execute.
        started = self._now()
        run = run.model_copy(update={"status": "running", "started_at": started, "updated_at": started})
        self.command_run_repo.update(run)

        argv = [command, *args]
        env = {"PATH": os.environ.get("PATH", "")}
        try:
            result = runner(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return self._record_timed_out(run, actor_email, exc, timeout_seconds)
        except (FileNotFoundError, OSError) as exc:
            return self._record_failed(run, actor_email, f"could not execute command: {exc}")
        except Exception as exc:  # defensive: any unexpected runner error
            return self._record_failed(run, actor_email, f"runner error: {exc}")

        return self._record_completed(run, actor_email, result)

    # ---------- terminal recorders ----------

    def _cap(self) -> int:
        cap = config.COMMAND_RUNNER_MAX_OUTPUT_BYTES
        return max(0, cap)

    def _per_stream_cap(self) -> int:
        return self._cap() // 2

    def _record_blocked(
        self, run: CommandRun, actor_email: str | None, reason: str
    ) -> CommandRun:
        now = self._now()
        updated = run.model_copy(
            update={
                "status": "blocked",
                "conclusion": "blocked",
                "completed_at": now,
                "updated_at": now,
                "error_message": reason,
            }
        )
        self.command_run_repo.update(updated)
        self.audit_writer.write(
            "command_run_blocked",
            "command_run",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": updated.workspace_id,
                "command": updated.command,
                "args": updated.args,
                "reason": reason,
            },
        )
        return updated

    def _record_failed(
        self, run: CommandRun, actor_email: str | None, reason: str
    ) -> CommandRun:
        now = self._now()
        updated = run.model_copy(
            update={
                "status": "failed",
                "conclusion": "failure",
                "completed_at": now,
                "updated_at": now,
                "error_message": reason,
            }
        )
        self.command_run_repo.update(updated)
        self.audit_writer.write(
            "command_run_failed",
            "command_run",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": updated.workspace_id,
                "command": updated.command,
                "reason": reason,
            },
        )
        return updated

    def _record_timed_out(
        self,
        run: CommandRun,
        actor_email: str | None,
        exc: subprocess.TimeoutExpired,
        timeout_seconds: int,
    ) -> CommandRun:
        now = self._now()
        # TimeoutExpired may carry partial output
        stdout = exc.output if isinstance(exc.output, str) else (
            exc.output.decode("utf-8", errors="replace") if exc.output else ""
        )
        stderr = exc.stderr if isinstance(exc.stderr, str) else (
            exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        )
        cap = self._per_stream_cap()
        stdout_t = _truncate(stdout or "", cap)
        stderr_t = _truncate(stderr or "", cap)
        artifact_id = self._maybe_save_artifact(stdout, stderr, now)
        updated = run.model_copy(
            update={
                "status": "timed_out",
                "conclusion": "timed_out",
                "completed_at": now,
                "updated_at": now,
                "stdout": stdout_t,
                "stderr": stderr_t,
                "output_summary": (stdout_t or stderr_t or "")[:240] or None,
                "artifact_id": artifact_id,
                "error_message": f"timed out after {timeout_seconds}s",
            }
        )
        self.command_run_repo.update(updated)
        self.audit_writer.write(
            "command_run_timed_out",
            "command_run",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": updated.workspace_id,
                "command": updated.command,
                "timeout_seconds": timeout_seconds,
            },
        )
        return updated

    def _record_completed(
        self,
        run: CommandRun,
        actor_email: str | None,
        result: subprocess.CompletedProcess,
    ) -> CommandRun:
        now = self._now()
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        cap = self._per_stream_cap()
        stdout_t = _truncate(stdout, cap)
        stderr_t = _truncate(stderr, cap)
        exit_code = int(result.returncode)
        conclusion = "success" if exit_code == 0 else "failure"
        status = "completed" if exit_code == 0 else "failed"
        artifact_id = self._maybe_save_artifact(stdout, stderr, now)
        updated = run.model_copy(
            update={
                "status": status,
                "conclusion": conclusion,
                "exit_code": exit_code,
                "stdout": stdout_t,
                "stderr": stderr_t,
                "output_summary": (stdout_t or stderr_t or "")[:240] or None,
                "artifact_id": artifact_id,
                "completed_at": now,
                "updated_at": now,
            }
        )
        self.command_run_repo.update(updated)
        action = "command_run_completed" if status == "completed" else "command_run_failed"
        self.audit_writer.write(
            action,
            "command_run",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": updated.workspace_id,
                "command": updated.command,
                "exit_code": exit_code,
                "conclusion": conclusion,
            },
        )
        return updated

    def _maybe_save_artifact(
        self, stdout: str, stderr: str, now: datetime
    ) -> str | None:
        if not (stdout or stderr):
            return None
        cap = self._cap()
        combined = ""
        if stdout:
            combined += "=== stdout ===\n" + stdout
        if stderr:
            if combined:
                combined += "\n"
            combined += "=== stderr ===\n" + stderr
        if len(combined) > cap and cap > 0:
            combined = combined[: max(0, cap - len(TRUNCATION_MARKER))] + TRUNCATION_MARKER
        artifact = Artifact(
            id=str(uuid.uuid4()),
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="command_run_output",
            content=combined,
            created_at=now,
        )
        self.artifact_repo.save(artifact)
        return artifact.id

    # ---------- queries ----------

    def list_runs_by_workspace(self, workspace_id: str) -> list[CommandRun]:
        if self.workspace_repo.get(workspace_id) is None:
            raise WorkspaceNotFoundError(workspace_id)
        return self.command_run_repo.list_by_workspace(workspace_id)

    def list_runs_by_project(self, project_id: str) -> list[CommandRun]:
        self._require_project(project_id)
        return self.command_run_repo.list_by_project(project_id)

    def get_run(self, run_id: str) -> CommandRun:
        r = self.command_run_repo.get(run_id)
        if r is None:
            raise CommandRunNotFound(run_id)
        return r


__all__ = [
    "CommandRunnerService",
    "CommandRunnerDisabled",
    "CommandDefinitionNotFound",
    "CommandRunNotFound",
    "WorkspaceNotFoundError",
    "ProjectNotFoundError",
    "CodeRepositoryNotFoundError",
    "WorkspaceNotReady",
    "CommandValidationError",
    "CommandBlocked",
    "validate_command_executable",
    "resolve_cwd",
]
