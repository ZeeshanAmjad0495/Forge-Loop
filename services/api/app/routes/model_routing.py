from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..repositories_state import project_repo
from ..services.model_routing import (
    ModelRouteDecision,
    ModelRoutePreviewRequest,
    decide_route,
    routing_summary,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/model-route/preview",
    response_model=ModelRouteDecision,
)
def preview_model_route(
    project_id: str,
    body: ModelRoutePreviewRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return decide_route(body, project_id=project_id)


@router.get("/runtime/model-routing")
def get_model_routing(current_user: str = Depends(require_auth)):
    return routing_summary()
