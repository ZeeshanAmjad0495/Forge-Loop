from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RunnerType = Literal[
    "openhands",
    "aider",
    "cline",
    "opencode",
    "hermes",
    "openclaw",
    "manual",
    "custom",
]
ToolRunnerMode = Literal["local", "api", "manual", "dry_run"]
ToolRunTargetType = Literal[
    "requirement",
    "epic",
    "dev_task",
    "subtask",
    "check_run",
    "manual",
]
ToolRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ToolRunConclusion = Literal[
    "success",
    "failure",
    "neutral",
    "skipped",
    "requires_human_action",
]


class ToolRunnerDefinitionCreate(BaseModel):
    code_repository_id: str | None = None
    name: str
    runner_type: RunnerType
    enabled: bool = True
    mode: ToolRunnerMode = "dry_run"
    description: str = ""
    config: dict = {}


class ToolRunnerDefinitionUpdate(BaseModel):
    name: str | None = None
    runner_type: RunnerType | None = None
    enabled: bool | None = None
    mode: ToolRunnerMode | None = None
    description: str | None = None
    config: dict | None = None


class ToolRunnerDefinition(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    name: str
    runner_type: RunnerType
    enabled: bool = True
    mode: ToolRunnerMode = "dry_run"
    description: str = ""
    config: dict = {}
    created_at: datetime
    updated_at: datetime


class ToolRunnerDefinitionsDefaultsRequest(BaseModel):
    code_repository_id: str | None = None


class ToolRunnerDefinitionsDefaultsResponse(BaseModel):
    created: list[ToolRunnerDefinition]
    existing: list[ToolRunnerDefinition]


class ToolRunCreate(BaseModel):
    project_id: str
    code_repository_id: str | None = None
    tool_runner_definition_id: str | None = None
    target_type: ToolRunTargetType
    target_id: str
    runner_type: RunnerType
    mode: ToolRunnerMode
    status: ToolRunStatus = "completed"
    conclusion: ToolRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ToolRun(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    tool_runner_definition_id: str | None = None
    target_type: ToolRunTargetType
    target_id: str
    runner_type: RunnerType
    mode: ToolRunnerMode
    status: ToolRunStatus
    conclusion: ToolRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    artifact_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OpenHandsPreparePackageRequest(BaseModel):
    tool_runner_definition_id: str | None = None
    code_repository_id: str | None = None


class OpenHandsInstructionPackage(BaseModel):
    schema_version: str = "1"
    runner: Literal["openhands"] = "openhands"
    mode: Literal["dry_run"] = "dry_run"
    project: dict
    repository: dict | None = None
    dev_task: dict
    context: dict
    safety: dict | None = None
    instructions: list[str]


class OpenHandsPrepareResponse(BaseModel):
    tool_run: ToolRun
    instruction_package: OpenHandsInstructionPackage


class OpenHandsRecordResultRequest(BaseModel):
    summary: str = ""
    output: str = ""
    conclusion: ToolRunConclusion = "neutral"
