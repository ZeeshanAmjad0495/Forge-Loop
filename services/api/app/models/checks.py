from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CheckType = Literal[
    "tests",
    "build",
    "lint",
    "typecheck",
    "coverage",
    "security_sast",
    "dependency_scan",
    "secret_scan",
    "container_scan",
    "accessibility",
    "e2e",
    "custom",
]
CheckSeverity = Literal["info", "warning", "blocking"]
CheckRunTargetType = Literal[
    "project",
    "requirement",
    "epic",
    "dev_task",
    "subtask",
    "pull_request",
    "manual",
]
CheckRunStatus = Literal["pending", "running", "completed", "failed"]
CheckRunConclusion = Literal["success", "failure", "neutral", "skipped", "cancelled"]


class CheckDefinitionCreate(BaseModel):
    code_repository_id: str | None = None
    name: str
    check_type: CheckType
    command: str = ""
    required: bool = True
    enabled: bool = True
    severity: CheckSeverity = "blocking"
    description: str = ""


class CheckDefinitionUpdate(BaseModel):
    name: str | None = None
    check_type: CheckType | None = None
    command: str | None = None
    required: bool | None = None
    enabled: bool | None = None
    severity: CheckSeverity | None = None
    description: str | None = None


class CheckDefinition(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    name: str
    check_type: CheckType
    command: str = ""
    required: bool = True
    enabled: bool = True
    severity: CheckSeverity = "blocking"
    description: str = ""
    created_at: datetime
    updated_at: datetime


class CheckDefinitionsFromSafetyProfileRequest(BaseModel):
    code_repository_id: str | None = None


class CheckRunCreate(BaseModel):
    project_id: str
    code_repository_id: str | None = None
    check_definition_id: str | None = None
    target_type: CheckRunTargetType
    target_id: str
    status: CheckRunStatus = "completed"
    conclusion: CheckRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CheckRun(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    check_definition_id: str | None = None
    target_type: CheckRunTargetType
    target_id: str
    status: CheckRunStatus
    conclusion: CheckRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    artifact_id: str | None = None
    command_run_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CheckDefinitionsFromSafetyProfileResponse(BaseModel):
    created: list[CheckDefinition]
    existing: list[CheckDefinition]


class CheckExecutionRequest(BaseModel):
    workspace_id: str
    target_type: CheckRunTargetType = "manual"
    target_id: str | None = None
    timeout_seconds: int | None = None


class CheckExecutionResponse(BaseModel):
    check_run: CheckRun
    command_run: "CommandRun"  # type: ignore[name-defined]


# Late import to resolve forward reference without circular import at module load.
from .commands import CommandRun  # noqa: E402

CheckExecutionResponse.model_rebuild()
