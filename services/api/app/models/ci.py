from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CIEventProvider = Literal[
    "github_actions",
    "gitlab_ci",
    "circleci",
    "manual",
    "custom",
]
CIEventStatus = Literal["queued", "in_progress", "completed", "failed"]
CIEventConclusion = Literal[
    "success",
    "failure",
    "cancelled",
    "skipped",
    "timed_out",
    "neutral",
    "unknown",
]


class CIEventCreate(BaseModel):
    code_repository_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    check_run_id: str | None = None
    provider: CIEventProvider
    external_run_id: str | None = None
    workflow_name: str | None = None
    job_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    status: CIEventStatus
    conclusion: CIEventConclusion
    failure_summary: str | None = None
    logs_excerpt: str | None = None
    raw_payload: dict | None = None


class CIEvent(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    check_run_id: str | None = None
    provider: CIEventProvider
    external_run_id: str | None = None
    workflow_name: str | None = None
    job_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    status: CIEventStatus
    conclusion: CIEventConclusion
    failure_summary: str | None = None
    logs_excerpt: str | None = None
    raw_payload: dict | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime


CIAnalysisStatus = Literal["pending", "running", "completed", "failed"]
CIAnalysisConclusion = Literal[
    "flaky_test",
    "code_regression",
    "dependency_issue",
    "configuration_issue",
    "infrastructure_issue",
    "unknown",
    "needs_human_review",
]


class CIAnalysisCreate(BaseModel):
    provider: str | None = None
    expensive_approved: bool = False


class CIAnalysis(BaseModel):
    id: str
    project_id: str
    ci_event_id: str
    provider: str
    model: str
    status: CIAnalysisStatus
    conclusion: CIAnalysisConclusion | None = None
    summary: str = ""
    likely_root_causes: list[str] = []
    suggested_fixes: list[str] = []
    affected_areas: list[str] = []
    recommended_next_action: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
