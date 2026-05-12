from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..llm import ProviderError, get_default_provider_name, get_provider_by_name
from ..models import (
    ArchitectureReview,
    ArchitectureReviewCreate,
    ArchitectureReviewGenerateRequest,
    ArchitectureReviewUpdate,
)
from ..repositories_state import (
    architecture_review_repo,
    artifact_repo,
    audit_writer,
    project_repo,
)
from ..services.architecture_reviews import (
    archive_review,
    create_review,
    generate_review,
    update_review,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post(
    "/architecture-reviews",
    response_model=ArchitectureReview,
    status_code=201,
)
def create_architecture_review(
    body: ArchitectureReviewCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    review = create_review(architecture_review_repo, body=body)
    audit_writer.write(
        action="architecture_review_created",
        target_type="architecture_review",
        target_id=review.id,
        project_id=review.project_id,
        actor_email=current_user,
        details={
            "target_type": review.target_type,
            "target_id": review.target_id,
            "status": review.status,
        },
    )
    return review


@router.get("/architecture-reviews", response_model=list[ArchitectureReview])
def list_architecture_reviews(
    project_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    if target_type is not None and target_id is not None:
        items = architecture_review_repo.list_by_target(target_type, target_id)
    elif project_id is not None:
        _ensure_project(project_id)
        items = architecture_review_repo.list_by_project(project_id)
    else:
        items = architecture_review_repo.list_all()
    if status is not None:
        items = [r for r in items if r.status == status]
    if target_type is not None and target_id is None:
        items = [r for r in items if r.target_type == target_type]
    return items


@router.get(
    "/projects/{project_id}/architecture-reviews",
    response_model=list[ArchitectureReview],
)
def list_architecture_reviews_for_project(
    project_id: str,
    target_type: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = architecture_review_repo.list_by_project(project_id)
    if target_type is not None:
        items = [r for r in items if r.target_type == target_type]
    if status is not None:
        items = [r for r in items if r.status == status]
    return items


@router.get(
    "/architecture-reviews/{review_id}",
    response_model=ArchitectureReview,
)
def get_architecture_review(
    review_id: str,
    current_user: str = Depends(require_auth),
):
    review = architecture_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Architecture review not found")
    return review


@router.patch(
    "/architecture-reviews/{review_id}",
    response_model=ArchitectureReview,
)
def patch_architecture_review(
    review_id: str,
    body: ArchitectureReviewUpdate,
    current_user: str = Depends(require_auth),
):
    review = architecture_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Architecture review not found")
    updated = update_review(architecture_review_repo, review, body)
    audit_writer.write(
        action="architecture_review_updated",
        target_type="architecture_review",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"status": updated.status},
    )
    return updated


@router.post(
    "/architecture-reviews/{review_id}/archive",
    response_model=ArchitectureReview,
)
def archive_architecture_review(
    review_id: str,
    current_user: str = Depends(require_auth),
):
    review = architecture_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Architecture review not found")
    archived = archive_review(architecture_review_repo, review)
    audit_writer.write(
        action="architecture_review_archived",
        target_type="architecture_review",
        target_id=archived.id,
        project_id=archived.project_id,
        actor_email=current_user,
    )
    return archived


@router.post(
    "/architecture-reviews/generate",
    response_model=ArchitectureReview,
    status_code=201,
)
def generate_architecture_review(
    body: ArchitectureReviewGenerateRequest,
    provider_name: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    resolved = provider_name or get_default_provider_name()
    try:
        provider = get_provider_by_name(resolved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    review, _artifact = generate_review(
        architecture_review_repo,
        artifact_repo,
        provider,
        body=body,
    )
    audit_writer.write(
        action="architecture_review_generated",
        target_type="architecture_review",
        target_id=review.id,
        project_id=review.project_id,
        actor_email=current_user,
        details={
            "target_type": review.target_type,
            "status": review.status,
            "provider": review.provider,
            "model": review.model,
        },
    )
    return review
