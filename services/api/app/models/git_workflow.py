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


__all__ = [
    "GitCommitCreate",
    "GitCommitRecord",
    "GitCommitStatus",
    "GitInspectionResponse",
    "WorkspaceBranch",
    "WorkspaceBranchCreate",
    "WorkspaceBranchResponse",
    "WorkspaceBranchStatus",
]
