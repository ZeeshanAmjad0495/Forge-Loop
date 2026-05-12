"""Human feedback analytics (Release 10, Task 59).

Lightweight counters over ReviewFeedback / RevisionWorkItem data. No live
GitHub sync, no LLM summarization, no charts.
"""

from __future__ import annotations

from collections import Counter

from ..models import ReviewFeedback, RevisionWorkItem
from ..repositories import ReviewFeedbackRepository, RevisionWorkItemRepository


def _empty_metrics() -> dict:
    return {
        "total_feedback_items": 0,
        "open_feedback_items": 0,
        "resolved_feedback_items": 0,
        "blocking_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "category_counts": {},
        "source_counts": {},
        "status_counts": {},
        "revision_items_created": 0,
        "revision_items_resolved": 0,
    }


def _compute_from_feedback(items: list[ReviewFeedback]) -> dict:
    metrics = _empty_metrics()
    metrics["total_feedback_items"] = len(items)
    metrics["open_feedback_items"] = sum(1 for f in items if f.status == "open")
    metrics["resolved_feedback_items"] = sum(
        1 for f in items if f.status == "resolved"
    )
    metrics["blocking_count"] = sum(1 for f in items if f.severity == "blocking")
    metrics["warning_count"] = sum(1 for f in items if f.severity == "warning")
    metrics["info_count"] = sum(1 for f in items if f.severity == "info")
    metrics["category_counts"] = dict(Counter(f.category for f in items))
    metrics["source_counts"] = dict(Counter(f.source for f in items))
    metrics["status_counts"] = dict(Counter(f.status for f in items))
    return metrics


def _merge_revision_counts(
    metrics: dict, revisions: list[RevisionWorkItem]
) -> dict:
    metrics["revision_items_created"] = len(revisions)
    metrics["revision_items_resolved"] = sum(
        1 for r in revisions if getattr(r, "status", None) == "resolved"
    )
    return metrics


def analytics_for_project(
    review_feedback_repo: ReviewFeedbackRepository,
    revision_work_item_repo: RevisionWorkItemRepository,
    *,
    project_id: str,
) -> dict:
    items = review_feedback_repo.list_by_project(project_id)
    metrics = _compute_from_feedback(items)
    revisions = revision_work_item_repo.list_by_project(project_id)
    return _merge_revision_counts(metrics, revisions)


def analytics_for_pr_draft(
    review_feedback_repo: ReviewFeedbackRepository,
    revision_work_item_repo: RevisionWorkItemRepository,
    *,
    pr_draft_id: str,
) -> dict:
    items = review_feedback_repo.list_by_pr_draft(pr_draft_id)
    metrics = _compute_from_feedback(items)
    revisions = revision_work_item_repo.list_by_pr_draft(pr_draft_id)
    return _merge_revision_counts(metrics, revisions)
