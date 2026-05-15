"""C3: real Kody review execution — submit a diff to Kodus and poll results.

Ties :mod:`kody_client` (the verified Kodus CLI-key HTTP boundary) to the
``PullRequestReview`` lifecycle:

- ``submit`` : pending -> running (async job) or pending -> completed (sync).
- ``poll``   : running -> completed (map issues -> findings) or running ->
  failed (error recorded). Still-running jobs are returned unchanged.

Gated by ``KODY_REVIEW_ENABLED`` + a resolvable team CLI key (secret
provider first). Never logs the key. Kodus issue severities are mapped to
ForgeLoop finding severities and an overall review conclusion is derived.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from .. import config as _config
from ..models import KodyReviewRunRequest, PullRequestReview, PullRequestReviewFinding
from ..pr_review.kody import is_allowed_review_status_transition
from ..repositories_state import audit_writer, pr_review_repo
from . import secrets as _secrets
from .kody_client import (
    KODY_CLIENT,
    KodyAuthError,
    KodyError,
    KodyNotFoundError,
    KodyRateLimitError,
    KodyValidationError,
)

_BLOCKING = {"critical", "high", "blocker", "error", "severe"}
_WARNING = {"medium", "moderate", "warn", "warning", "major"}
_FORGELOOP_CATEGORIES = {
    "security", "tests", "correctness", "maintainability",
    "performance", "scope", "style",
}
_TERMINAL_OK = {"completed", "success", "succeeded", "done"}
_TERMINAL_FAIL = {"failed", "error", "errored", "cancelled", "canceled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_key() -> str:
    return (
        _secrets.get_secret("KODY_API_KEY") or _config.KODY_API_KEY or ""
    ).strip()


def _map_severity(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if s in _BLOCKING:
        return "blocking"
    if s in _WARNING:
        return "warning"
    return "info"


def _map_category(raw: str | None) -> str | None:
    c = (raw or "").strip().lower()
    return c if c in _FORGELOOP_CATEGORIES else None


def _issues_to_findings(issues: list) -> list[PullRequestReviewFinding]:
    findings: list[PullRequestReviewFinding] = []
    for it in issues or []:
        if not isinstance(it, dict):
            continue
        findings.append(
            PullRequestReviewFinding(
                severity=_map_severity(it.get("severity")),
                category=_map_category(it.get("category")),
                message=str(it.get("message") or "").strip() or "(no message)",
                file_path=it.get("file"),
                line=it.get("line") if isinstance(it.get("line"), int) else None,
                recommendation=(
                    it.get("recommendation") or it.get("suggestion")
                ),
            )
        )
    return findings


def _derive_conclusion(findings: list[PullRequestReviewFinding]) -> str:
    if any(f.severity == "blocking" for f in findings):
        return "changes_requested"
    if findings:
        return "comment_only"
    return "approved"


def _gate(review_id: str) -> PullRequestReview:
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    if not _config.KODY_REVIEW_ENABLED:
        raise HTTPException(status_code=409, detail="KODY_REVIEW_DISABLED")
    if not _resolve_key():
        raise HTTPException(
            status_code=409, detail="KODY_API_KEY_NOT_CONFIGURED"
        )
    return review


def _map_client_error(exc: KodyError) -> HTTPException:
    if isinstance(exc, KodyAuthError):
        return HTTPException(status_code=502, detail="kody_auth_failed")
    if isinstance(exc, KodyValidationError):
        return HTTPException(status_code=422, detail="kody_validation_failed")
    if isinstance(exc, KodyRateLimitError):
        return HTTPException(status_code=429, detail="kody_rate_limited")
    if isinstance(exc, KodyNotFoundError):
        return HTTPException(status_code=502, detail="kody_not_found")
    return HTTPException(status_code=502, detail="kody_error")


def _record_completed(
    review: PullRequestReview,
    result: dict,
    actor_email: str,
) -> PullRequestReview:
    findings = _issues_to_findings(result.get("issues") or [])
    conclusion = _derive_conclusion(findings)
    now = _now()
    updated = review.model_copy(update={
        "status": "completed",
        "conclusion": conclusion,
        "summary": str(result.get("summary") or "").strip() or review.summary,
        "findings": findings,
        "raw_output": json.dumps(result, sort_keys=True)[:200000],
        "completed_at": now,
        "started_at": review.started_at or now,
        "updated_at": now,
        "error_message": None,
    })
    pr_review_repo.update(updated)
    audit_writer.write(
        "pr_review_completed", "pr_review", review.id,
        project_id=review.project_id, actor_email=actor_email,
        details={
            "pr_draft_id": review.pr_draft_id,
            "review_id": review.id,
            "provider": "kody",
            "conclusion": conclusion,
            "findings_count": len(findings),
        },
    )
    return updated


def submit(
    review_id: str,
    body: KodyReviewRunRequest,
    actor_email: str,
) -> PullRequestReview:
    review = _gate(review_id)
    if review.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"review status {review.status!r} is not 'pending'",
        )
    if not (body.diff or "").strip():
        raise HTTPException(status_code=400, detail="diff is required")

    async_mode = (
        _config.KODY_ASYNC if body.async_mode is None else bool(body.async_mode)
    )
    key = _resolve_key()
    try:
        resp = KODY_CLIENT.start_review(
            api_key=key,
            diff=body.diff,
            config=body.config,
            branch=body.branch,
            commit_sha=body.commit_sha,
            merge_base_sha=body.merge_base_sha,
            git_remote=body.git_remote,
            user_email=body.user_email,
            async_mode=async_mode,
        )
    except KodyError as exc:
        raise _map_client_error(exc) from None

    job_id = resp.get("jobId") or resp.get("job_id")
    now = _now()

    if job_id:
        updated = review.model_copy(update={
            "status": "running",
            "started_at": review.started_at or now,
            "updated_at": now,
            "raw_output": json.dumps({"kody_job_id": job_id}),
            "error_message": None,
        })
        pr_review_repo.update(updated)
        audit_writer.write(
            "pr_review_requested", "pr_review", review.id,
            project_id=review.project_id, actor_email=actor_email,
            details={
                "pr_draft_id": review.pr_draft_id,
                "review_id": review.id,
                "provider": "kody",
                "kody_job_id": job_id,
            },
        )
        return updated

    # Synchronous result.
    return _record_completed(review, resp, actor_email)


def poll(review_id: str, actor_email: str) -> PullRequestReview:
    review = _gate(review_id)
    if review.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"review status {review.status!r} is not 'running'",
        )
    try:
        meta = json.loads(review.raw_output or "{}")
    except (ValueError, TypeError):
        meta = {}
    job_id = meta.get("kody_job_id")
    if not job_id:
        raise HTTPException(
            status_code=400,
            detail="review has no kody_job_id (was it submitted via Kody?)",
        )

    key = _resolve_key()
    try:
        resp = KODY_CLIENT.get_review_job(api_key=key, job_id=job_id)
    except KodyError as exc:
        raise _map_client_error(exc) from None

    status = str(resp.get("status") or "").strip().lower()
    if status in _TERMINAL_OK:
        result = resp.get("result")
        if not isinstance(result, dict):
            result = {"summary": "", "issues": []}
        return _record_completed(review, result, actor_email)

    if status in _TERMINAL_FAIL:
        now = _now()
        if not is_allowed_review_status_transition(review.status, "failed"):
            raise HTTPException(
                status_code=400,
                detail=f"cannot fail review in status {review.status!r}",
            )
        err = str(resp.get("error") or "kody review failed")[:2000]
        updated = review.model_copy(update={
            "status": "failed",
            "updated_at": now,
            "completed_at": now,
            "error_message": err,
        })
        pr_review_repo.update(updated)
        audit_writer.write(
            "pr_review_recorded", "pr_review", review.id,
            project_id=review.project_id, actor_email=actor_email,
            details={
                "pr_draft_id": review.pr_draft_id,
                "review_id": review.id,
                "provider": "kody",
                "kody_job_status": status,
            },
        )
        return updated

    # Still pending/running — return unchanged so the caller polls again.
    return review


__all__ = ["submit", "poll"]
