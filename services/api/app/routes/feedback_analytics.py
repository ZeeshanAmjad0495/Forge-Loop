from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..repositories_state import (
    pr_draft_repo,
    project_repo,
    review_feedback_repo,
    revision_work_item_repo,
)
from ..services.feedback_analytics import (
    analytics_for_pr_draft,
    analytics_for_project,
)

router = APIRouter()


@router.get("/projects/{project_id}/feedback-analytics")
def project_feedback_analytics(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        "metrics": analytics_for_project(
            review_feedback_repo,
            revision_work_item_repo,
            project_id=project_id,
        ),
    }


@router.get("/pr-drafts/{pr_draft_id}/feedback-analytics")
def pr_draft_feedback_analytics(
    pr_draft_id: str,
    current_user: str = Depends(require_auth),
):
    if pr_draft_repo.get(pr_draft_id) is None:
        raise HTTPException(status_code=404, detail="PR draft not found")
    return {
        "pr_draft_id": pr_draft_id,
        "metrics": analytics_for_pr_draft(
            review_feedback_repo,
            revision_work_item_repo,
            pr_draft_id=pr_draft_id,
        ),
    }
