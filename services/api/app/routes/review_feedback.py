from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..models import (
    ReviewFeedback,
    ReviewFeedbackCreate,
    ReviewFeedbackImportResponse,
    ReviewFeedbackResolve,
    ReviewFeedbackUpdate,
    RevisionPlanResponse,
    RevisionWorkItem,
    RevisionWorkItemCreate,
    RevisionWorkItemUpdate,
)
from ..services import review_feedback as _feedback_service
from ..services import revision_work_items as _revision_service

router = APIRouter()


@router.post(
    "/pr-drafts/{pr_draft_id}/feedback-items",
    response_model=ReviewFeedback,
    status_code=201,
)
def create_review_feedback(
    pr_draft_id: str,
    body: ReviewFeedbackCreate,
    current_user: str = Depends(require_auth),
):
    return _feedback_service.create(pr_draft_id, body, current_user)


@router.get(
    "/pr-drafts/{pr_draft_id}/feedback-items",
    response_model=list[ReviewFeedback],
)
def list_review_feedback_for_draft(
    pr_draft_id: str,
    _: str = Depends(require_auth),
):
    return _feedback_service.list_by_pr_draft(pr_draft_id)


@router.get(
    "/review-feedback/{feedback_id}",
    response_model=ReviewFeedback,
)
def get_review_feedback(
    feedback_id: str,
    _: str = Depends(require_auth),
):
    return _feedback_service.get(feedback_id)


@router.patch(
    "/review-feedback/{feedback_id}",
    response_model=ReviewFeedback,
)
def patch_review_feedback(
    feedback_id: str,
    body: ReviewFeedbackUpdate,
    current_user: str = Depends(require_auth),
):
    return _feedback_service.patch(feedback_id, body, current_user)


@router.post(
    "/pr-reviews/{review_id}/feedback-items/from-findings",
    response_model=ReviewFeedbackImportResponse,
    status_code=201,
)
def import_review_feedback_from_findings(
    review_id: str,
    current_user: str = Depends(require_auth),
):
    return _feedback_service.import_from_findings(review_id, current_user)


@router.post(
    "/review-feedback/{feedback_id}/plan-revision",
    response_model=RevisionPlanResponse,
    status_code=201,
)
def plan_review_feedback_revision(
    feedback_id: str,
    body: RevisionWorkItemCreate,
    current_user: str = Depends(require_auth),
):
    return _revision_service.plan(feedback_id, body, current_user)


@router.post(
    "/review-feedback/{feedback_id}/resolve",
    response_model=ReviewFeedback,
)
def resolve_review_feedback(
    feedback_id: str,
    body: ReviewFeedbackResolve,
    current_user: str = Depends(require_auth),
):
    return _feedback_service.resolve(feedback_id, body, current_user)


@router.get(
    "/pr-drafts/{pr_draft_id}/revision-work-items",
    response_model=list[RevisionWorkItem],
)
def list_revision_work_items_for_draft(
    pr_draft_id: str,
    _: str = Depends(require_auth),
):
    return _revision_service.list_by_pr_draft(pr_draft_id)


@router.get(
    "/revision-work-items/{revision_work_item_id}",
    response_model=RevisionWorkItem,
)
def get_revision_work_item(
    revision_work_item_id: str,
    _: str = Depends(require_auth),
):
    return _revision_service.get(revision_work_item_id)


@router.patch(
    "/revision-work-items/{revision_work_item_id}",
    response_model=RevisionWorkItem,
)
def patch_revision_work_item(
    revision_work_item_id: str,
    body: RevisionWorkItemUpdate,
    current_user: str = Depends(require_auth),
):
    return _revision_service.patch(revision_work_item_id, body, current_user)
