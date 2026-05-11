"""Task 39: ReviewFeedback model.

A ReviewFeedback row captures a single actionable feedback item attached
to a PullRequestDraft. Source can be a human reviewer, an imported finding
from a PullRequestReview, manual entry, or another tool. ForgeLoop does
not sync live GitHub comments; feedback is entered or imported explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ReviewFeedbackSource = Literal["human", "kody", "github", "manual", "custom"]
ReviewFeedbackStatus = Literal[
    "open",
    "accepted",
    "revision_planned",
    "in_progress",
    "resolved",
    "rejected",
    "deferred",
]
ReviewFeedbackSeverity = Literal["blocking", "warning", "info"]
ReviewFeedbackCategory = Literal[
    "correctness",
    "tests",
    "security",
    "maintainability",
    "performance",
    "scope",
    "style",
    "documentation",
    "other",
]


class ReviewFeedbackCreate(BaseModel):
    pr_review_id: str | None = None
    source: ReviewFeedbackSource = "human"
    author: str | None = None
    severity: ReviewFeedbackSeverity = "warning"
    category: ReviewFeedbackCategory = "other"
    summary: str
    details: str | None = None
    file_path: str | None = None
    line: int | None = None
    recommendation: str | None = None


class ReviewFeedbackUpdate(BaseModel):
    status: ReviewFeedbackStatus | None = None
    severity: ReviewFeedbackSeverity | None = None
    category: ReviewFeedbackCategory | None = None
    summary: str | None = None
    details: str | None = None
    recommendation: str | None = None


class ReviewFeedbackResolve(BaseModel):
    resolution_summary: str


class ReviewFeedback(BaseModel):
    id: str
    project_id: str
    pr_draft_id: str
    pr_review_id: str | None = None
    source: ReviewFeedbackSource
    author: str | None = None
    status: ReviewFeedbackStatus = "open"
    severity: ReviewFeedbackSeverity
    category: ReviewFeedbackCategory
    summary: str
    details: str | None = None
    file_path: str | None = None
    line: int | None = None
    recommendation: str | None = None
    revision_work_item_id: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolution_summary: str | None = None


class ReviewFeedbackImportResponse(BaseModel):
    pr_review_id: str
    pr_draft_id: str
    created: int
    skipped: int
    feedback_items: list[ReviewFeedback]


__all__ = [
    "ReviewFeedback",
    "ReviewFeedbackCategory",
    "ReviewFeedbackCreate",
    "ReviewFeedbackImportResponse",
    "ReviewFeedbackResolve",
    "ReviewFeedbackSeverity",
    "ReviewFeedbackSource",
    "ReviewFeedbackStatus",
    "ReviewFeedbackUpdate",
]
