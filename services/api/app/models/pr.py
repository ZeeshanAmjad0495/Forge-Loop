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
    # Task 38: additive fields populated by the GitHub publication service.
    workspace_id: str | None = None
    workspace_branch_id: str | None = None
    github_owner: str | None = None
    github_repo: str | None = None
    last_published_at: datetime | None = None


# Task 38: GitHub draft PR creation request/response.


class GitHubDraftCreate(BaseModel):
    workspace_id: str
    workspace_branch_id: str
    approval_id: str | None = None
    remote_name: str = "origin"
    push_branch: bool = True
    draft: bool = True


class GitHubPublicationSummary(BaseModel):
    pushed: bool
    remote_name: str | None = None
    pushed_branch: str | None = None
    push_exit_code: int | None = None
    github_owner: str
    github_repo: str
    external_pr_url: str
    external_pr_number: int
    head: str
    base: str
    draft: bool


class GitHubDraftCreationResponse(BaseModel):
    pr_draft: "PullRequestDraft"
    publication_summary: GitHubPublicationSummary


class DraftPrPipelineStep(BaseModel):
    name: str
    status: Literal["ok", "skipped_flag_off", "blocked", "failed"]
    detail: str = ""


class DraftPrPipelineResult(BaseModel):
    """Task 100: consolidated end-to-end draft-PR pipeline outcome.

    The pipeline orchestrates already-gated steps; it never merges,
    marks-ready, deploys, force-pushes, or bypasses protected branches.
    The terminal state is at most 'draft PR opened, awaiting human
    review'.
    """

    dev_task_id: str
    project_id: str
    enabled: bool
    final_status: Literal[
        "disabled",
        "blocked",
        "branch_ready",
        "pushed",
        "draft_pr_opened",
        "failed",
    ]
    pr_draft_id: str | None = None
    steps: list[DraftPrPipelineStep] = []
    awaiting_human_review: bool = True


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


class KodyReviewRunRequest(BaseModel):
    # The unified diff to review (Kodus reviews a diff, not a repo).
    diff: str
    config: dict | None = None
    branch: str | None = None
    commit_sha: str | None = None
    merge_base_sha: str | None = None
    git_remote: str | None = None
    user_email: str | None = None
    async_mode: bool | None = None  # None -> config.KODY_ASYNC


class PullRequestReviewComplete(BaseModel):
    conclusion: PullRequestReviewConclusion
    summary: str | None = None
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None


class PullRequestReviewRemediateRequest(BaseModel):
    # Optional overrides; default to the PR draft's workspace/branch.
    workspace_id: str | None = None
    workspace_branch_id: str | None = None
    approval_required: bool = True


class PullRequestReviewRemediation(BaseModel):
    review_id: str
    pr_draft_id: str
    project_id: str
    imported_feedback_ids: list[str]
    driving_feedback_id: str
    revision_work_item_id: str
    revision_work_item_status: str
    requires_approval: bool
    workspace_id: str
    workspace_branch_id: str | None = None


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
