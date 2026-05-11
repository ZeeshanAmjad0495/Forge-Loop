from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PullRequestDraftStatus = Literal[
    "draft_prepared",
    "awaiting_approval",
    "approved_for_creation",
    "created",
    "failed",
    "closed",
    "cancelled",
]
PullRequestDraftProvider = Literal["manual", "local", "github"]


class PullRequestDraftCreate(BaseModel):
    code_repository_id: str
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    title: str | None = None
    body: str | None = None
    source_branch: str | None = None
    target_branch: str = "main"
    provider: PullRequestDraftProvider = "manual"


class PullRequestDraftUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    status: PullRequestDraftStatus | None = None
    external_pr_url: str | None = None
    external_pr_number: int | None = None
    error_message: str | None = None


class PullRequestDraft(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    title: str
    body: str
    source_branch: str
    target_branch: str = "main"
    status: PullRequestDraftStatus = "draft_prepared"
    provider: PullRequestDraftProvider = "manual"
    external_pr_url: str | None = None
    external_pr_number: int | None = None
    created_by: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None


PullRequestReviewProvider = Literal["kody", "manual", "custom"]
PullRequestReviewStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]
PullRequestReviewConclusion = Literal[
    "approved",
    "changes_requested",
    "comment_only",
    "failed",
    "skipped",
    "requires_human_review",
]
PullRequestReviewFindingSeverity = Literal["blocking", "warning", "info"]
PullRequestReviewFindingCategory = Literal[
    "security",
    "tests",
    "correctness",
    "maintainability",
    "performance",
    "scope",
    "style",
]


class PullRequestReviewFinding(BaseModel):
    severity: PullRequestReviewFindingSeverity | None = None
    category: PullRequestReviewFindingCategory | None = None
    message: str
    file_path: str | None = None
    line: int | None = None
    recommendation: str | None = None


class PullRequestReviewCreate(BaseModel):
    provider: PullRequestReviewProvider = "kody"
    mode: Literal["manual", "prepare"] = "prepare"
    summary: str | None = None
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None
    conclusion: PullRequestReviewConclusion | None = None
    external_review_url: str | None = None


class PullRequestReviewUpdate(BaseModel):
    status: PullRequestReviewStatus | None = None
    conclusion: PullRequestReviewConclusion | None = None
    summary: str | None = None
    findings: list[PullRequestReviewFinding] | None = None
    recommendations: str | None = None
    raw_output: str | None = None
    external_review_url: str | None = None
    error_message: str | None = None


class PullRequestReviewComplete(BaseModel):
    conclusion: PullRequestReviewConclusion
    summary: str | None = None
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None


class PullRequestReview(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    pr_draft_id: str
    provider: PullRequestReviewProvider
    status: PullRequestReviewStatus
    conclusion: PullRequestReviewConclusion | None = None
    summary: str = ""
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    external_review_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
