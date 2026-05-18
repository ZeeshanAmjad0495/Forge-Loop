from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import PlanningRunCreate, PlanningRunResponse
from ..planning_agent import run_planning_agent
from .common import resolve_routed_provider_or_400
from ..repositories_state import (
    agent_run_repo,
    artifact_repo,
    project_context_repo,
    repo,
)

router = APIRouter()


@router.post("/tickets/{ticket_id}/planning-runs", response_model=PlanningRunResponse, status_code=201)
def create_planning_run(
    ticket_id: str,
    body: PlanningRunCreate | None = Body(default=None),
    _: str = Depends(require_auth),
):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    provider, _route_decision = resolve_routed_provider_or_400(
        "planning",
        body.provider if body else None,
        project_id=ticket.project_id,
        source_type="ticket",
        source_id=ticket.id,
        expensive_approved=(body.expensive_approved if body else False),
    )
    context = None
    if ticket.project_id:
        context = project_context_repo.get(ticket.project_id)
    run, artifact = run_planning_agent(ticket, provider, agent_run_repo, artifact_repo, context)
    updated = ticket.model_copy(update={"status": "brief_generated", "updated_at": datetime.now(timezone.utc)})
    repo.save(updated)
    return PlanningRunResponse(agent_run=run, artifact=artifact)
