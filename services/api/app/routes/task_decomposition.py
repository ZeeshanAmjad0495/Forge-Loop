from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import TaskDecompositionResponse, TaskDecompositionRunCreate
from ..repositories_state import (
    agent_run_repo,
    analysis_repo,
    artifact_repo,
    audit_writer,
    dev_task_repo,
    project_context_repo,
    repo,
    requirement_repo,
    subtask_repo,
)
from ..task_decomposition_agent import (
    run_task_decomposition_for_requirement,
    run_task_decomposition_for_ticket,
)
from .common import resolve_routed_provider_or_400

router = APIRouter()


@router.post(
    "/requirements/{requirement_id}/task-decompositions",
    response_model=TaskDecompositionResponse,
    status_code=201,
)
def create_task_decomposition_for_requirement(
    requirement_id: str,
    body: TaskDecompositionRunCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    provider, _route_decision = resolve_routed_provider_or_400(
        "task_decomposition",
        body.provider if body else None,
        project_id=requirement.project_id,
        source_type="requirement",
        source_id=requirement.id,
    )
    context = project_context_repo.get(requirement.project_id)
    latest_analysis = analysis_repo.get_latest_by_requirement(requirement_id)
    run, artifact, dev_tasks, subtasks = run_task_decomposition_for_requirement(
        requirement, provider, agent_run_repo, artifact_repo, dev_task_repo, subtask_repo,
        context, latest_analysis,
    )
    audit_writer.write(
        "task_decomposition_created", "task_decomposition", run.id,
        project_id=requirement.project_id, actor_email=current_user,
        details={"dev_task_count": len(dev_tasks)},
    )
    return TaskDecompositionResponse(
        agent_run=run, artifact=artifact, dev_tasks=dev_tasks, subtasks=subtasks
    )


@router.post(
    "/tickets/{ticket_id}/task-decompositions",
    response_model=TaskDecompositionResponse,
    status_code=201,
)
def create_task_decomposition_for_ticket(
    ticket_id: str,
    body: TaskDecompositionRunCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    provider, _route_decision = resolve_routed_provider_or_400(
        "task_decomposition",
        body.provider if body else None,
        project_id=ticket.project_id,
        source_type="ticket",
        source_id=ticket.id,
    )
    context = None
    if ticket.project_id:
        context = project_context_repo.get(ticket.project_id)
    latest_analysis = analysis_repo.get_latest_by_ticket(ticket_id)
    run, artifact, dev_tasks, subtasks = run_task_decomposition_for_ticket(
        ticket, provider, agent_run_repo, artifact_repo, dev_task_repo, subtask_repo,
        context, latest_analysis,
    )
    audit_writer.write(
        "task_decomposition_created", "task_decomposition", run.id,
        project_id=ticket.project_id, actor_email=current_user,
        details={"dev_task_count": len(dev_tasks)},
    )
    return TaskDecompositionResponse(
        agent_run=run, artifact=artifact, dev_tasks=dev_tasks, subtasks=subtasks
    )
