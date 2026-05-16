from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    KodyReviewRunRequest,
    PullRequestReview,
    PullRequestReviewComplete,
    PullRequestReviewCreate,
    PullRequestReviewRemediateRequest,
    PullRequestReviewRemediation,
    PullRequestReviewUpdate,
)
from ..repositories_state import pr_draft_repo, pr_review_repo
from ..services import (
    kody_review_execution,
    pr_review_remediation,
    pr_review_workflow,
)

router = APIRouter()


@router.post(
    "/pr-drafts/{pr_draft_id}/reviews",
    response_model=PullRequestReview,
    status_code=201,
)
def create_pr_review(
    pr_draft_id: str,
    body: PullRequestReviewCreate,
    current_user: str = Depends(require_auth),
):
    return pr_review_workflow.create_review(pr_draft_id, body, current_user)


@router.get(
    "/pr-drafts/{pr_draft_id}/reviews",
    response_model=list[PullRequestReview],
)
def list_pr_draft_reviews(pr_draft_id: str, _: str = Depends(require_auth)):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return pr_review_repo.list_by_pr_draft(pr_draft_id)


@router.get("/pr-reviews/{review_id}", response_model=PullRequestReview)
def get_pr_review(review_id: str, _: str = Depends(require_auth)):
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    return review


@router.patch("/pr-reviews/{review_id}", response_model=PullRequestReview)
def patch_pr_review(
    review_id: str,
    body: PullRequestReviewUpdate,
    current_user: str = Depends(require_auth),
):
    return pr_review_workflow.patch_review(review_id, body, current_user)


@router.post(
    "/pr-reviews/{review_id}/complete",
    response_model=PullRequestReview,
)
def complete_pr_review(
    review_id: str,
    body: PullRequestReviewComplete,
    current_user: str = Depends(require_auth),
):
    return pr_review_workflow.complete_review(review_id, body, current_user)


@router.post(
    "/pr-reviews/{review_id}/kody/run",
    response_model=PullRequestReview,
)
def run_kody_review(
    review_id: str,
    body: KodyReviewRunRequest,
    current_user: str = Depends(require_auth),
):
    return kody_review_execution.submit(review_id, body, current_user)


@router.post(
    "/pr-reviews/{review_id}/kody/poll",
    response_model=PullRequestReview,
)
def poll_kody_review(
    review_id: str,
    current_user: str = Depends(require_auth),
):
    return kody_review_execution.poll(review_id, current_user)


@router.post(
    "/pr-reviews/{review_id}/remediate",
    response_model=PullRequestReviewRemediation,
    status_code=201,
)
def remediate_pr_review(
    review_id: str,
    body: PullRequestReviewRemediateRequest | None = None,
    current_user: str = Depends(require_auth),
):
    """Close the review loop: turn a completed review's findings into an
    approval-gated remediation work item that re-enters the pipeline."""
    return pr_review_remediation.remediate(review_id, body, current_user)
