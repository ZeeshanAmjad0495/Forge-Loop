"""Task 39: RevisionWorkItem model.

A small, dedicated work-item row for tracking the operator's response to a
ReviewFeedback. Sibling of DevTask, not a reuse: DevTask is born from
task-decomposition runs, while a RevisionWorkItem is born from a feedback
item and references an existing workspace + branch + (optionally) a
DevTask/Subtask. Its status enum is distinct from DevTaskStatus.

Execution itself flows through the existing Task 36/37/38 endpoints.
RevisionWorkItem provides traceability, not orchestration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .review_feedback import ReviewFeedback


RevisionWorkItemStatus = Literal[
    "proposed",
    "approved",
    "in_progress",
    "implemented",
    "checks_passed",
    "ready_for_review",
    "resolved",
    "rejected",
]


class RevisionWorkItemCreate(BaseModel):
    workspace_id: str
    workspace_branch_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    title: str | None = None
    description: str | None = None
    approval_required: bool = True


class RevisionWorkItemUpdate(BaseModel):
    status: RevisionWorkItemStatus | None = None
    title: str | None = None
    description: str | None = None
    workspace_branch_id: str | None = None


class RevisionWorkItem(BaseModel):
    id: str
    project_id: str
    pr_draft_id: str
    review_feedback_id: str
    dev_task_id: str | None = None
    subtask_id: str | None = None
    workspace_id: str
    workspace_branch_id: str | None = None
    title: str
    description: str
    status: RevisionWorkItemStatus = "proposed"
    requires_approval: bool = True
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    resolved_at: datetime | None = None


class RevisionPlanResponse(BaseModel):
    review_feedback: ReviewFeedback
    revision_work_item: RevisionWorkItem


__all__ = [
    "RevisionPlanResponse",
    "RevisionWorkItem",
    "RevisionWorkItemCreate",
    "RevisionWorkItemStatus",
    "RevisionWorkItemUpdate",
]
