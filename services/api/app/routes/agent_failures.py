from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    AgentFailureRecord,
    AgentFailureRecordCreate,
    AgentFailureRecordResolve,
    AgentFailureRecordUpdate,
    AgentFailureSummary,
)
from ..repositories_state import agent_failure_record_repo, project_repo
from ..services.agent_failures import (
    create_failure,
    resolve_failure,
    summary_for_project,
    update_failure,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/agent-failures",
    response_model=AgentFailureRecord,
    status_code=201,
)
def create_agent_failure(
    project_id: str,
    body: AgentFailureRecordCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return create_failure(
        agent_failure_record_repo, project_id=project_id, body=body
    )


@router.get(
    "/projects/{project_id}/agent-failures",
    response_model=list[AgentFailureRecord],
)
def list_agent_failures(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return agent_failure_record_repo.list_by_project(project_id)


@router.get(
    "/agent-failures/{failure_id}",
    response_model=AgentFailureRecord,
)
def get_agent_failure(
    failure_id: str,
    current_user: str = Depends(require_auth),
):
    record = agent_failure_record_repo.get(failure_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Agent failure not found")
    return record


@router.patch(
    "/agent-failures/{failure_id}",
    response_model=AgentFailureRecord,
)
def patch_agent_failure(
    failure_id: str,
    body: AgentFailureRecordUpdate,
    current_user: str = Depends(require_auth),
):
    record = agent_failure_record_repo.get(failure_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Agent failure not found")
    return update_failure(agent_failure_record_repo, record, body)


@router.post(
    "/agent-failures/{failure_id}/resolve",
    response_model=AgentFailureRecord,
)
def resolve_agent_failure(
    failure_id: str,
    body: AgentFailureRecordResolve,
    current_user: str = Depends(require_auth),
):
    record = agent_failure_record_repo.get(failure_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Agent failure not found")
    return resolve_failure(agent_failure_record_repo, record, body)


@router.get(
    "/projects/{project_id}/agent-failures/summary",
    response_model=AgentFailureSummary,
)
def get_agent_failure_summary(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return summary_for_project(agent_failure_record_repo, project_id=project_id)
