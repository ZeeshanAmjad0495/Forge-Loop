from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..repositories_state import audit_writer, project_repo
from ..services.runner_router import (
    RunnerRouteDecision,
    RunnerRoutePreviewRequest,
    decide_runner,
    runner_routing_summary,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/runner-route/preview",
    response_model=RunnerRouteDecision,
)
def preview_runner_route(
    project_id: str,
    body: RunnerRoutePreviewRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    decision = decide_runner(body)
    audit_writer.write(
        "runner_route_previewed",
        "project",
        project_id,
        project_id=project_id,
        actor_email=current_user,
        details={
            "source_type": body.source_type,
            "source_id": body.source_id,
            "runner_name": decision.runner_name,
            "reason": decision.reason,
            "task_complexity": decision.task_complexity,
            "requires_human_approval": decision.requires_human_approval,
            "fallback_runner": decision.fallback_runner,
        },
    )
    return decision


@router.get("/runtime/runner-routing")
def get_runner_routing(current_user: str = Depends(require_auth)):
    return runner_routing_summary()
