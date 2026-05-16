"""(c) Review-findings revision loop — close the loop, don't just surface.

A completed PullRequestReview with actionable findings can be turned, in
one approval-gated step, into a tracked remediation work item that
re-enters the existing execute -> commit -> QA -> re-review pipeline.

This is pure orchestration over the EXISTING services — no parallel
system, no new persistence:
  1. review_feedback.import_from_findings  (review.findings -> ReviewFeedback)
  2. revision_work_items.plan              (feedback -> proposed,
     approval-gated RevisionWorkItem bound to the PR's workspace/branch)

It never auto-executes (RevisionWorkItem is `proposed` + requires
approval; execution still flows through the approval-gated OpenHands/
Aider endpoints on the bound branch — consistent with the no-auto-
remediation work-safe rule).
"""

from __future__ import annotations

from fastapi import HTTPException

from ..models import (
    PullRequestReviewRemediateRequest,
    PullRequestReviewRemediation,
    RevisionWorkItemCreate,
)
from ..repositories_state import (
    audit_writer,
    pr_draft_repo,
    pr_review_repo,
    review_feedback_repo,
)
from . import review_feedback as _review_feedback
from . import revision_work_items as _revisions

_SEVERITY_RANK = {"blocking": 0, "warning": 1, "info": 2}
_ACTIONABLE_CONCLUSIONS = {"changes_requested", "requires_human_review"}


def _findings_checklist(feedback_items) -> str:
    lines = [
        "Remediate the following review findings. Address every BLOCKING "
        "item; resolve WARNING items or justify. Keep the change minimal "
        "and re-run the QA gate.",
        "",
    ]
    for fb in sorted(
        feedback_items, key=lambda f: _SEVERITY_RANK.get(f.severity, 1)
    ):
        loc = f" [{fb.file_path}:{fb.line}]" if fb.file_path else ""
        rec = f" — fix: {fb.recommendation}" if fb.recommendation else ""
        lines.append(
            f"- [{fb.severity}/{fb.category}]{loc} {fb.summary}{rec}"
        )
    return "\n".join(lines)


def remediate(
    review_id: str,
    body: PullRequestReviewRemediateRequest | None,
    actor_email: str,
) -> PullRequestReviewRemediation:
    body = body or PullRequestReviewRemediateRequest()
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    if review.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=(
                f"review status {review.status!r} is not 'completed' — "
                "nothing to remediate yet"
            ),
        )
    has_blocking = any(
        getattr(f, "severity", None) == "blocking"
        for f in (review.findings or [])
    )
    if review.conclusion not in _ACTIONABLE_CONCLUSIONS and not has_blocking:
        raise HTTPException(
            status_code=400,
            detail=(
                "review has no actionable findings (not changes_requested / "
                "requires_human_review and no blocking finding) — nothing "
                "to remediate"
            ),
        )

    draft = pr_draft_repo.get(review.pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    workspace_id = body.workspace_id or draft.workspace_id
    workspace_branch_id = (
        body.workspace_branch_id or draft.workspace_branch_id
    )
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "PR draft has no associated workspace; supply workspace_id "
                "to plan the remediation"
            ),
        )

    # 1) Materialise findings -> ReviewFeedback (idempotent: import dedups;
    #    on re-invocation fall back to the review's existing feedback).
    imp = _review_feedback.import_from_findings(review_id, actor_email)
    feedback_items = list(imp.feedback_items)
    if not feedback_items:
        feedback_items = [
            fb
            for fb in review_feedback_repo.list_by_pr_draft(review.pr_draft_id)
            if fb.pr_review_id == review_id
            and fb.status not in ("resolved", "rejected")
        ]
    if not feedback_items:
        raise HTTPException(
            status_code=400,
            detail="no actionable feedback could be derived from this review",
        )

    # 2) Driving feedback = highest severity; plan ONE approval-gated
    #    revision work item carrying the full findings checklist.
    driving = sorted(
        feedback_items, key=lambda f: _SEVERITY_RANK.get(f.severity, 1)
    )[0]
    plan_resp = _revisions.plan(
        driving.id,
        RevisionWorkItemCreate(
            workspace_id=workspace_id,
            workspace_branch_id=workspace_branch_id,
            title=f"Remediate review {review_id[:8]} ({len(feedback_items)} finding(s))",
            description=_findings_checklist(feedback_items),
            approval_required=bool(body.approval_required),
        ),
        actor_email,
    )
    item = plan_resp.revision_work_item

    audit_writer.write(
        "pr_review_remediation_planned",
        "pr_review",
        review_id,
        project_id=review.project_id,
        actor_email=actor_email,
        details={
            "pr_draft_id": review.pr_draft_id,
            "revision_work_item_id": item.id,
            "driving_feedback_id": driving.id,
            "feedback_count": len(feedback_items),
            "requires_approval": item.requires_approval,
            "workspace_id": workspace_id,
            "workspace_branch_id": workspace_branch_id,
        },
    )

    return PullRequestReviewRemediation(
        review_id=review_id,
        pr_draft_id=review.pr_draft_id,
        project_id=review.project_id,
        imported_feedback_ids=[f.id for f in feedback_items],
        driving_feedback_id=driving.id,
        revision_work_item_id=item.id,
        revision_work_item_status=item.status,
        requires_approval=item.requires_approval,
        workspace_id=workspace_id,
        workspace_branch_id=workspace_branch_id,
    )


__all__ = ["remediate"]
