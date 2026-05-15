"""CheckDefinition → CommandRun execution bridge (Task 35).

Connects ForgeLoop deterministic CheckDefinitions to the Safe Command Runner
so a check can be executed inside a registered workspace and the result
recorded as a CheckRun linked to the underlying CommandRun.

This service never spawns subprocesses itself. All execution is delegated to
``CommandRunnerService.run``, which enforces the Task 34 safety policy
(allowlist, no shell, timeout, output cap, audit + artifact trail).
"""

from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import (
    CheckExecutionRequest,
    CheckRun,
    CheckRunConclusion,
    CheckRunStatus,
    CommandRun,
    CommandRunCreate,
)
from ..models.commands import arg_invalid_reason, command_invalid_reason
from .command_runner import (
    CommandDefinitionNotFound,
    CommandRunnerDisabled,
    CommandRunnerService,
    CommandValidationError,
    WorkspaceNotFoundError,
)


class CheckDefinitionNotFound(LookupError):
    pass


class CheckExecutionValidationError(ValueError):
    pass


@dataclass
class CheckExecutionResult:
    check_run: CheckRun
    command_run: CommandRun


def parse_check_command(command: str) -> tuple[str, list[str]]:
    """Parse a CheckDefinition.command string into (executable, args).

    Uses ``shlex.split`` then re-validates each token through the same
    shell-metacharacter checks the CommandDefinition validators enforce.
    Raises ``CheckExecutionValidationError`` on any unsafe / ambiguous input.
    """
    if not command or not command.strip():
        raise CheckExecutionValidationError("check definition has no command")
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError as exc:
        raise CheckExecutionValidationError(f"could not parse command: {exc}") from exc
    if not tokens:
        raise CheckExecutionValidationError("check definition has no command")
    cmd, args = tokens[0], tokens[1:]
    reason = command_invalid_reason(cmd)
    if reason:
        raise CheckExecutionValidationError(f"unsafe command: {reason}")
    for a in args:
        reason = arg_invalid_reason(a)
        if reason:
            raise CheckExecutionValidationError(f"unsafe arg {a!r}: {reason}")
    return cmd, args


_TERMINAL_FAILED: tuple[CheckRunStatus, CheckRunConclusion] = ("failed", "failure")
_TERMINAL_PASSED: tuple[CheckRunStatus, CheckRunConclusion] = ("completed", "success")


def _map_command_run_to_check_status(
    command_run: CommandRun,
) -> tuple[CheckRunStatus, CheckRunConclusion]:
    if command_run.conclusion == "success":
        return _TERMINAL_PASSED
    # All other terminal CommandRun outcomes (failure, timed_out, blocked,
    # neutral, skipped) map to CheckRun failed/failure to preserve the
    # existing CheckRunStatus enum without invention.
    return _TERMINAL_FAILED


def _summary_for(command_run: CommandRun) -> str:
    conclusion = command_run.conclusion
    if conclusion == "success":
        return f"Command exited 0 ({command_run.command})"
    if conclusion == "failure":
        exit_code = command_run.exit_code
        if exit_code is not None:
            return f"Command exited {exit_code} ({command_run.command})"
        if command_run.error_message:
            return f"Command failed: {command_run.error_message}"
        return f"Command failed ({command_run.command})"
    if conclusion == "timed_out":
        return command_run.error_message or "Command timed out"
    if conclusion == "blocked":
        return f"Blocked: {command_run.error_message or 'command rejected'}"
    return command_run.error_message or f"Command outcome: {conclusion}"


@dataclass
class CheckExecutionService:
    check_definition_repo: object
    check_run_repo: object
    workspace_repo: object
    project_repo: object
    command_runner: CommandRunnerService
    audit_writer: object

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def execute(
        self,
        check_definition_id: str,
        body: CheckExecutionRequest,
        *,
        actor_email: str | None,
    ) -> CheckExecutionResult:
        definition = self.check_definition_repo.get(check_definition_id)
        if definition is None:
            raise CheckDefinitionNotFound(check_definition_id)

        workspace = self.workspace_repo.get(body.workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError(body.workspace_id)

        if workspace.project_id != definition.project_id:
            raise CheckExecutionValidationError(
                "workspace project does not match check definition project"
            )

        if (
            definition.code_repository_id is not None
            and workspace.code_repository_id is not None
            and definition.code_repository_id != workspace.code_repository_id
        ):
            raise CheckExecutionValidationError(
                "workspace code repository does not match check definition code repository"
            )

        if not definition.enabled:
            raise CheckExecutionValidationError("check definition is disabled")

        if getattr(definition, "shell", False):
            # Opt-in shell mode: run the raw command through bash so it can
            # use &&, pipes, env prefixes, etc. `bash` is still validated
            # against the command allowlist by the runner. The command
            # string itself is intentionally NOT token-validated here —
            # that is the whole point of the opt-in.
            if not definition.command or not definition.command.strip():
                raise CheckExecutionValidationError("check definition has no command")
            cmd, args = "bash", ["-lc", definition.command]
            shell_mode = True
        else:
            cmd, args = parse_check_command(definition.command)
            shell_mode = False

        target_id = body.target_id or definition.id
        cmr_create = CommandRunCreate(
            shell=shell_mode,
            command_definition_id=None,
            command=cmd,
            args=args,
            target_type=body.target_type,
            target_id=target_id,
            timeout_seconds=body.timeout_seconds,
            working_directory=None,
        )

        self.audit_writer.write(
            "check_execution_requested",
            "check_definition",
            definition.id,
            project_id=definition.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "check_definition_id": definition.id,
                "target_type": body.target_type,
                "target_id": target_id,
            },
        )

        # Delegate execution to the Safe Command Runner. This path handles
        # blocked/timed-out/failed/success uniformly and returns a terminal
        # CommandRun record. CommandRunnerDisabled propagates up.
        command_run = self.command_runner.run(
            workspace.id,
            cmr_create,
            actor_email=actor_email,
        )

        status, conclusion = _map_command_run_to_check_status(command_run)
        summary = _summary_for(command_run)
        now = self._now()
        started = command_run.started_at or command_run.created_at
        check_run = CheckRun(
            id=str(uuid.uuid4()),
            project_id=definition.project_id,
            code_repository_id=definition.code_repository_id,
            check_definition_id=definition.id,
            target_type=body.target_type,
            target_id=target_id,
            status=status,
            conclusion=conclusion,
            summary=summary,
            output=command_run.output_summary,
            artifact_id=command_run.artifact_id,
            command_run_id=command_run.id,
            started_at=started,
            completed_at=command_run.completed_at,
            created_at=now,
            updated_at=now,
        )
        self.check_run_repo.save(check_run)

        if command_run.conclusion == "success":
            action = "check_execution_completed"
        elif command_run.conclusion == "blocked":
            action = "check_execution_blocked"
        else:
            action = "check_execution_failed"
        self.audit_writer.write(
            action,
            "check_run",
            check_run.id,
            project_id=check_run.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "check_definition_id": definition.id,
                "command_run_id": command_run.id,
                "command_run_conclusion": command_run.conclusion,
                "exit_code": command_run.exit_code,
            },
        )
        return CheckExecutionResult(check_run=check_run, command_run=command_run)


__all__ = [
    "CheckExecutionService",
    "CheckExecutionResult",
    "CheckDefinitionNotFound",
    "CheckExecutionValidationError",
    "parse_check_command",
    # Re-export from command_runner so route handlers can catch a single
    # cohesive set of execution errors.
    "WorkspaceNotFoundError",
    "CommandRunnerDisabled",
    "CommandDefinitionNotFound",
    "CommandValidationError",
]
