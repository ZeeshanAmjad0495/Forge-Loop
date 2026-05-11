"""Task 39: ReviewFeedback service.

Manual feedback creation, import from PullRequestReview.findings (with
content-based dedup), safe-field PATCH with status-transition validator,
and resolution. Never modifies PullRequestDraft / PullRequestReview rows.

No network. No git. No GitHub calls. No OpenHands. No LLM.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from ..models import (
    Artifact,
    ReviewFeedback,
    ReviewFeedbackCreate,
    ReviewFeedbackImportResponse,
    ReviewFeedbackResolve,
    ReviewFeedbackUpdate,
)


# Caps to keep records small and predictable.
_SUMMARY_CAP = 500
_DETAILS_CAP = 4000
_RECOMMENDATION_CAP = 2000
_RESOLUTION_CAP = 1000


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"accepted", "rejected", "deferred", "revision_planned"},
    "accepted": {"revision_planned", "in_progress", "resolved", "rejected", "deferred"},
    "revision_planned": {"in_progress", "resolved", "rejected", "deferred"},
    "in_progress": {"resolved", "deferred", "rejected"},
    "deferred": {"open", "accepted", "revision_planned"},
    "rejected": set(),
    "resolved": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cap(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    s = str(text)
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def _validate_summary(summary: str) -> str:
    if not isinstance(summary, str) or not summary.strip():
        raise HTTPException(status_code=400, detail="summary is empty")
    return _cap(summary.strip(), _SUMMARY_CAP) or ""


def _validate_line(line: int | None) -> int | None:
    if line is None:
        return None
    try:
        n = int(line)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="line must be an integer")
    if n < 0 or n > 10_000_000:
        raise HTTPException(status_code=400, detail="line is out of range")
    return n


def _dedup_hash(*, severity: str, category: str, file_path: str | None,
                line: int | None, summary: str) -> str:
    key = "|".join([
        severity,
        category,
        (file_path or "").strip().lower(),
        str(line) if line is not None else "",
        summary.strip().lower(),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _provider_to_source(provider: str | None) -> str:
    if provider == "kody":
        return "kody"
    if provider == "manual":
        return "manual"
    if provider == "custom":
        return "custom"
    return "manual"


@dataclass
class ReviewFeedbackService:
    pr_draft_repo: object
    pr_review_repo: object
    project_repo: object
    review_feedback_repo: object
    revision_work_item_repo: object
    artifact_repo: object
    audit_writer: object

    # --- shared loaders ---------------------------------------------------

    def _require_pr_draft(self, pr_draft_id: str):
        draft = self.pr_draft_repo.get(pr_draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="PullRequestDraft not found")
        return draft

    def _require_feedback(self, feedback_id: str) -> ReviewFeedback:
        fb = self.review_feedback_repo.get(feedback_id)
        if fb is None:
            raise HTTPException(status_code=404, detail="ReviewFeedback not found")
        return fb

    # --- public operations ------------------------------------------------

    def create(
        self,
        pr_draft_id: str,
        body: ReviewFeedbackCreate,
        actor_email: str,
    ) -> ReviewFeedback:
        draft = self._require_pr_draft(pr_draft_id)
        summary = _validate_summary(body.summary)
        details = _cap(body.details, _DETAILS_CAP)
        recommendation = _cap(body.recommendation, _RECOMMENDATION_CAP)
        line = _validate_line(body.line)

        if body.pr_review_id is not None:
            review = self.pr_review_repo.get(body.pr_review_id)
            if review is None:
                raise HTTPException(status_code=404, detail="PullRequestReview not found")
            if review.pr_draft_id != pr_draft_id:
                raise HTTPException(
                    status_code=400,
                    detail="PullRequestReview does not belong to PR draft",
                )

        now = _now()
        feedback = ReviewFeedback(
            id=str(uuid.uuid4()),
            project_id=draft.project_id,
            pr_draft_id=draft.id,
            pr_review_id=body.pr_review_id,
            source=body.source,
            author=body.author or actor_email,
            status="open",
            severity=body.severity,
            category=body.category,
            summary=summary,
            details=details,
            file_path=body.file_path,
            line=line,
            recommendation=recommendation,
            revision_work_item_id=None,
            created_at=now,
            updated_at=now,
            resolved_at=None,
            resolution_summary=None,
        )
        self.review_feedback_repo.save(feedback)
        self.audit_writer.write(
            "review_feedback_created",
            "review_feedback",
            feedback.id,
            project_id=draft.project_id,
            actor_email=actor_email,
            details={
                "pr_draft_id": draft.id,
                "pr_review_id": body.pr_review_id,
                "severity": feedback.severity,
                "category": feedback.category,
                "source": feedback.source,
            },
        )
        return feedback

    def list_by_pr_draft(self, pr_draft_id: str) -> list[ReviewFeedback]:
        self._require_pr_draft(pr_draft_id)
        return self.review_feedback_repo.list_by_pr_draft(pr_draft_id)

    def get(self, feedback_id: str) -> ReviewFeedback:
        return self._require_feedback(feedback_id)

    def patch(
        self,
        feedback_id: str,
        body: ReviewFeedbackUpdate,
        actor_email: str,
    ) -> ReviewFeedback:
        feedback = self._require_feedback(feedback_id)
        if feedback.status in ("resolved", "rejected"):
            raise HTTPException(
                status_code=400,
                detail=f"ReviewFeedback in status {feedback.status!r} cannot be modified",
            )
        patch = body.model_dump(exclude_unset=True)
        if not patch:
            return feedback
        updates: dict = {}
        target_status: str | None = None
        if "status" in patch and patch["status"] is not None:
            target_status = patch["status"]
            if target_status != feedback.status and target_status not in _ALLOWED_TRANSITIONS.get(
                feedback.status, set()
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Disallowed status transition: {feedback.status} -> {target_status}"
                    ),
                )
            updates["status"] = target_status
        if "severity" in patch and patch["severity"] is not None:
            updates["severity"] = patch["severity"]
        if "category" in patch and patch["category"] is not None:
            updates["category"] = patch["category"]
        if "summary" in patch and patch["summary"] is not None:
            updates["summary"] = _validate_summary(patch["summary"])
        if "details" in patch:
            updates["details"] = _cap(patch["details"], _DETAILS_CAP)
        if "recommendation" in patch:
            updates["recommendation"] = _cap(patch["recommendation"], _RECOMMENDATION_CAP)
        updates["updated_at"] = _now()
        updated = feedback.model_copy(update=updates)
        self.review_feedback_repo.update(updated)

        action = "review_feedback_updated"
        if target_status == "rejected":
            action = "review_feedback_rejected"
        elif target_status == "deferred":
            action = "review_feedback_deferred"
        self.audit_writer.write(
            action,
            "review_feedback",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "changed_fields": list(patch.keys()),
                "from_status": feedback.status,
                "to_status": target_status,
            },
        )
        return updated

    def import_from_findings(
        self,
        review_id: str,
        actor_email: str,
    ) -> ReviewFeedbackImportResponse:
        review = self.pr_review_repo.get(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="PullRequestReview not found")
        draft = self._require_pr_draft(review.pr_draft_id)

        existing = self.review_feedback_repo.list_by_pr_review(review.id)
        existing_hashes: set[str] = set()
        for fb in existing:
            existing_hashes.add(_dedup_hash(
                severity=fb.severity,
                category=fb.category,
                file_path=fb.file_path,
                line=fb.line,
                summary=fb.summary,
            ))

        source = _provider_to_source(getattr(review, "provider", None))
        created: list[ReviewFeedback] = []
        skipped = 0
        now = _now()

        for finding in (review.findings or []):
            severity = finding.severity if finding.severity in ("blocking", "warning", "info") else "warning"
            category = finding.category if finding.category in {
                "correctness", "tests", "security", "maintainability", "performance",
                "scope", "style", "documentation", "other",
            } else "other"
            raw_msg = (finding.message or "").strip()
            if not raw_msg:
                skipped += 1
                continue
            summary = _cap(raw_msg, _SUMMARY_CAP) or ""
            details = _cap(raw_msg, _DETAILS_CAP)
            recommendation = _cap(finding.recommendation, _RECOMMENDATION_CAP)
            line = _validate_line(finding.line)

            h = _dedup_hash(
                severity=severity,
                category=category,
                file_path=finding.file_path,
                line=line,
                summary=summary,
            )
            if h in existing_hashes:
                skipped += 1
                continue
            existing_hashes.add(h)

            feedback = ReviewFeedback(
                id=str(uuid.uuid4()),
                project_id=draft.project_id,
                pr_draft_id=draft.id,
                pr_review_id=review.id,
                source=source,
                author=None,
                status="open",
                severity=severity,
                category=category,
                summary=summary,
                details=details,
                file_path=finding.file_path,
                line=line,
                recommendation=recommendation,
                revision_work_item_id=None,
                created_at=now,
                updated_at=now,
                resolved_at=None,
                resolution_summary=None,
            )
            self.review_feedback_repo.save(feedback)
            created.append(feedback)

        artifact_payload = json.dumps({
            "pr_review_id": review.id,
            "pr_draft_id": draft.id,
            "created": len(created),
            "skipped": skipped,
            "created_ids": [c.id for c in created],
        }, sort_keys=True)
        self.artifact_repo.save(Artifact(
            id=str(uuid.uuid4()),
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="review_feedback_import_summary",
            content=artifact_payload,
            created_at=now,
        ))
        self.audit_writer.write(
            "review_feedback_imported",
            "pr_review",
            review.id,
            project_id=draft.project_id,
            actor_email=actor_email,
            details={
                "pr_draft_id": draft.id,
                "created": len(created),
                "skipped": skipped,
            },
        )
        return ReviewFeedbackImportResponse(
            pr_review_id=review.id,
            pr_draft_id=draft.id,
            created=len(created),
            skipped=skipped,
            feedback_items=created,
        )

    def resolve(
        self,
        feedback_id: str,
        body: ReviewFeedbackResolve,
        actor_email: str,
    ) -> ReviewFeedback:
        feedback = self._require_feedback(feedback_id)
        if feedback.status in ("resolved", "rejected"):
            raise HTTPException(
                status_code=400,
                detail=f"ReviewFeedback in status {feedback.status!r} cannot be resolved",
            )
        summary_text = (body.resolution_summary or "").strip()
        if not summary_text:
            raise HTTPException(status_code=400, detail="resolution_summary is empty")
        capped = _cap(summary_text, _RESOLUTION_CAP)
        now = _now()
        updated = feedback.model_copy(update={
            "status": "resolved",
            "resolution_summary": capped,
            "resolved_at": now,
            "updated_at": now,
        })
        self.review_feedback_repo.save(updated)

        # If a linked revision work item exists and is not terminal, move it
        # to resolved. We do not modify PR draft / PR review state.
        if feedback.revision_work_item_id:
            item = self.revision_work_item_repo.get(feedback.revision_work_item_id)
            if item is not None and item.status not in ("resolved", "rejected"):
                self.revision_work_item_repo.update(item.model_copy(update={
                    "status": "resolved",
                    "resolved_at": now,
                    "updated_at": now,
                }))

        artifact_payload = json.dumps({
            "feedback_id": updated.id,
            "pr_draft_id": updated.pr_draft_id,
            "revision_work_item_id": updated.revision_work_item_id,
            "severity": updated.severity,
            "resolution_summary": capped,
        }, sort_keys=True)
        self.artifact_repo.save(Artifact(
            id=str(uuid.uuid4()),
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="review_feedback_resolution_summary",
            content=artifact_payload,
            created_at=now,
        ))
        self.audit_writer.write(
            "review_feedback_resolved",
            "review_feedback",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "pr_draft_id": updated.pr_draft_id,
                "revision_work_item_id": updated.revision_work_item_id,
                "severity": updated.severity,
            },
        )
        return updated


def _service() -> ReviewFeedbackService:
    from ..repositories_state import (
        artifact_repo,
        audit_writer,
        pr_draft_repo,
        pr_review_repo,
        project_repo,
        review_feedback_repo,
        revision_work_item_repo,
    )
    return ReviewFeedbackService(
        pr_draft_repo=pr_draft_repo,
        pr_review_repo=pr_review_repo,
        project_repo=project_repo,
        review_feedback_repo=review_feedback_repo,
        revision_work_item_repo=revision_work_item_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
    )


def create(pr_draft_id, body, actor_email):
    return _service().create(pr_draft_id, body, actor_email)


def list_by_pr_draft(pr_draft_id):
    return _service().list_by_pr_draft(pr_draft_id)


def get(feedback_id):
    return _service().get(feedback_id)


def patch(feedback_id, body, actor_email):
    return _service().patch(feedback_id, body, actor_email)


def import_from_findings(review_id, actor_email):
    return _service().import_from_findings(review_id, actor_email)


def resolve(feedback_id, body, actor_email):
    return _service().resolve(feedback_id, body, actor_email)


__all__ = [
    "ReviewFeedbackService",
    "create",
    "get",
    "import_from_findings",
    "list_by_pr_draft",
    "patch",
    "resolve",
]
