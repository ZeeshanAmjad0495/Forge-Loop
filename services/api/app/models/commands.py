from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CommandType = Literal[
    "test",
    "build",
    "lint",
    "typecheck",
    "coverage",
    "security_scan",
    "utility",
    "custom",
]

CommandRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "timed_out",
    "blocked",
    "cancelled",
]

CommandRunConclusion = Literal[
    "success",
    "failure",
    "neutral",
    "skipped",
    "blocked",
    "timed_out",
]

CommandRunTargetType = Literal[
    "project",
    "requirement",
    "epic",
    "dev_task",
    "subtask",
    "check_definition",
    "check_run",
    "tool_run",
    "manual",
]


SHELL_METACHARS: tuple[str, ...] = (
    "|",
    "&&",
    "||",
    ";",
    ">",
    ">>",
    "<",
    "$(",
    "`",
    "\n",
    "\r",
)


def _command_invalid_reason(command: str) -> str | None:
    if not command or not command.strip():
        return "command must be non-empty"
    if command != command.strip():
        return "command must not contain leading/trailing whitespace"
    if any(ch.isspace() for ch in command):
        return "command must not contain whitespace"
    if "/" in command or "\\" in command:
        return "command must be an executable name only (no path separators)"
    for token in SHELL_METACHARS:
        if token in command:
            return f"command must not contain shell metacharacter {token!r}"
    return None


def _arg_invalid_reason(arg: str) -> str | None:
    if not isinstance(arg, str):
        return "args must be strings"
    for token in SHELL_METACHARS:
        if token in arg:
            return f"arg must not contain shell metacharacter {token!r}"
    return None


command_invalid_reason = _command_invalid_reason
arg_invalid_reason = _arg_invalid_reason


def _working_directory_invalid_reason(wd: str | None) -> str | None:
    if wd is None:
        return None
    if wd == "":
        return "working_directory must be non-empty if provided"
    if wd.startswith("/") or (len(wd) > 1 and wd[1] == ":"):
        return "working_directory must be relative to workspace root"
    parts = wd.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return "working_directory must not contain '..'"
    return None


class CommandDefinitionCreate(BaseModel):
    workspace_id: str | None = None
    code_repository_id: str | None = None
    name: str = Field(min_length=1)
    command: str
    args: list[str] = []
    command_type: CommandType = "custom"
    enabled: bool = True
    requires_approval: bool = True
    timeout_seconds: int = 300
    working_directory: str | None = None
    description: str | None = None

    @field_validator("command")
    @classmethod
    def _validate_command(cls, v: str) -> str:
        reason = _command_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v

    @field_validator("args")
    @classmethod
    def _validate_args(cls, v: list[str]) -> list[str]:
        for a in v:
            reason = _arg_invalid_reason(a)
            if reason:
                raise ValueError(reason)
        return v

    @field_validator("working_directory")
    @classmethod
    def _validate_working_directory(cls, v: str | None) -> str | None:
        reason = _working_directory_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeout_seconds must be >= 1")
        return v


class CommandDefinitionUpdate(BaseModel):
    name: str | None = None
    command: str | None = None
    args: list[str] | None = None
    command_type: CommandType | None = None
    enabled: bool | None = None
    requires_approval: bool | None = None
    timeout_seconds: int | None = None
    working_directory: str | None = None
    description: str | None = None

    @field_validator("command")
    @classmethod
    def _validate_command(cls, v: str | None) -> str | None:
        if v is None:
            return v
        reason = _command_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v

    @field_validator("args")
    @classmethod
    def _validate_args(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for a in v:
            reason = _arg_invalid_reason(a)
            if reason:
                raise ValueError(reason)
        return v

    @field_validator("working_directory")
    @classmethod
    def _validate_working_directory(cls, v: str | None) -> str | None:
        if v is None:
            return v
        reason = _working_directory_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v < 1:
            raise ValueError("timeout_seconds must be >= 1")
        return v


class CommandDefinition(BaseModel):
    id: str
    project_id: str
    workspace_id: str | None = None
    code_repository_id: str | None = None
    name: str
    command: str
    args: list[str] = []
    command_type: CommandType
    enabled: bool
    requires_approval: bool
    timeout_seconds: int
    working_directory: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class CommandRunCreate(BaseModel):
    command_definition_id: str | None = None
    command: str | None = None
    args: list[str] | None = None
    target_type: CommandRunTargetType = "manual"
    target_id: str | None = None
    timeout_seconds: int | None = None
    working_directory: str | None = None

    @field_validator("command")
    @classmethod
    def _validate_command(cls, v: str | None) -> str | None:
        if v is None:
            return v
        reason = _command_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v

    @field_validator("args")
    @classmethod
    def _validate_args(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for a in v:
            reason = _arg_invalid_reason(a)
            if reason:
                raise ValueError(reason)
        return v

    @field_validator("working_directory")
    @classmethod
    def _validate_working_directory(cls, v: str | None) -> str | None:
        if v is None:
            return v
        reason = _working_directory_invalid_reason(v)
        if reason:
            raise ValueError(reason)
        return v


class CommandRun(BaseModel):
    id: str
    project_id: str
    workspace_id: str
    command_definition_id: str | None = None
    target_type: CommandRunTargetType
    target_id: str | None = None
    command: str
    args: list[str] = []
    status: CommandRunStatus
    conclusion: CommandRunConclusion | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    output_summary: str | None = None
    artifact_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
