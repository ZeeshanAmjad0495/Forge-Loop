from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AgentFailureSourceType = Literal[
    "command_run",
    "check_run",
    "tool_run",
    "pr_review",
    "review_feedback",
    "build_trial_stage",
    "manual",
]

AgentFailureCategory = Literal[
    "requirement_gap",
    "planning_error",
    "wrong_file_changed",
    "missing_tests",
    "failing_tests",
    "build_failure",
    "lint_failure",
    "typecheck_failure",
    "unsafe_path_touch",
    "command_blocked",
    "timeout",
    "provider_failure",
    "tool_failure",
    "git_failure",
    "github_failure",
    "review_failure",
    "memory_learning_failure",
    "cost_budget_exceeded",
    "unknown",
]

AgentFailureSeverity = Literal["blocker", "high", "medium", "low", "info"]
AgentFailureStatus = Literal["open", "acknowledged", "resolved", "dismissed"]
AgentFailureDetector = Literal["human", "system", "test", "review", "custom"]


class AgentFailureRecordCreate(BaseModel):
    source_type: AgentFailureSourceType = "manual"
    source_id: str | None = None
    trial_id: str | None = None
    category: AgentFailureCategory = "unknown"
    severity: AgentFailureSeverity = "medium"
    summary: str
    details: str | None = None
    detected_by: AgentFailureDetector = "human"


class AgentFailureRecordUpdate(BaseModel):
    category: AgentFailureCategory | None = None
    severity: AgentFailureSeverity | None = None
    summary: str | None = None
    details: str | None = None
    status: AgentFailureStatus | None = None
    resolution_summary: str | None = None


class AgentFailureRecordResolve(BaseModel):
    resolution_summary: str | None = None
    status: AgentFailureStatus = "resolved"


class AgentFailureRecord(BaseModel):
    id: str
    project_id: str
    source_type: AgentFailureSourceType
    source_id: str | None = None
    trial_id: str | None = None
    category: AgentFailureCategory = "unknown"
    severity: AgentFailureSeverity = "medium"
    summary: str
    details: str | None = None
    status: AgentFailureStatus = "open"
    detected_by: AgentFailureDetector = "human"
    resolution_summary: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentFailureSummary(BaseModel):
    project_id: str
    total: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    by_status: dict[str, int]
    by_source_type: dict[str, int]
