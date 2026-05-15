"""Models for Task 37: Local Git Branch Workflow.

Workspace-scoped, local-only. No remote, push, pull, fetch, merge, or PR. Task
38 will own GitHub interaction; Task 37 produces the local branch + commit
evidence Task 38 needs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


WorkspaceBranchStatus = Literal[
    "prepared",
    "active",
    "clean",
    "dirty",
    "committed",
    "failed",
    "archived",
]


class WorkspaceBranchCreate(BaseModel):
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    base_branch: str | None = None
    name: str | None = None
    approval_id: str | None = None


class WorkspaceBranch(BaseModel):
    id: str
    project_id: str
    workspace_id: str
    code_repository_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    name: str
    base_branch: str | None = None
    current_branch: str | None = None
    status: WorkspaceBranchStatus
    created_at: datetime
    updated_at: datetime
    last_inspected_at: datetime | None = None
    error_message: str | None = None


class GitInspectionResponse(BaseModel):
    workspace_id: str
    is_git_repo: bool
    current_branch: str | None = None
    base_branch: str | None = None
    dirty: bool = False
    changed_files: list[str] = []
    untracked_files: list[str] = []
    diff_stat: str = ""
    ahead_behind: None = None
    notes: list[str] = []
    git_workflow_enabled: bool = False
    git_commit_enabled: bool = False


class WorkspaceBranchResponse(BaseModel):
    workspace_branch: WorkspaceBranch
    inspection: GitInspectionResponse


GitCommitStatus = Literal["prepared", "committed", "failed"]


class GitCommitCreate(BaseModel):
    message: str
    approval_id: str | None = None
    include_paths: list[str] | None = None


class GitCommitRecord(BaseModel):
    id: str
    project_id: str
    workspace_id: str
    workspace_branch_id: str
    commit_sha: str | None = None
    message: str
    status: GitCommitStatus
    changed_files: list[str] = []
    diff_stat: str = ""
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


# ---------------------------------------------------------------------------
# B2: native multi-dev-task integration.
#
# Manual hand-merge of per-dev-task branches previously dropped a dev_task
# silently (DT-S4-3). The integration run takes an *explicit ordered* list of
# already-committed workspace branches, merges them onto a fresh integration
# branch, and reports every member's outcome. A conflict surfaces as a 409
# with the conflicting member + files — it is never skipped or hidden.
# ---------------------------------------------------------------------------


IntegrationMemberStatus = Literal[
    "pending",
    "merged",
    "conflict",
    "not_attempted",
]

IntegrationRunStatus = Literal["integrated", "conflict", "failed"]


class IntegrationMember(BaseModel):
    workspace_branch_id: str
    branch_name: str
    dev_task_id: str | None = None
    status: IntegrationMemberStatus = "pending"
    conflicting_files: list[str] = []
    detail: str | None = None


class IntegrationRunCreate(BaseModel):
    # Ordered list of already-committed WorkspaceBranch ids to integrate.
    source_branch_ids: list[str]
    base_branch: str | None = None
    name: str | None = None
    approval_id: str | None = None
    create_pr_draft: bool = False
    code_repository_id: str | None = None
    target_branch: str = "main"
    pr_title: str | None = None
    pr_body: str | None = None


class IntegrationRunResult(BaseModel):
    status: IntegrationRunStatus
    integration_branch: WorkspaceBranch
    base_branch: str
    members: list[IntegrationMember]
    commit_sha: str | None = None
    git_commit_record_id: str | None = None
    pr_draft_id: str | None = None
    diff_stat: str = ""
    notes: list[str] = []


__all__ = [
    "GitCommitCreate",
    "GitCommitRecord",
    "GitCommitStatus",
    "GitInspectionResponse",
    "IntegrationMember",
    "IntegrationMemberStatus",
    "IntegrationRunCreate",
    "IntegrationRunResult",
    "IntegrationRunStatus",
    "WorkspaceBranch",
    "WorkspaceBranchCreate",
    "WorkspaceBranchResponse",
    "WorkspaceBranchStatus",
]
