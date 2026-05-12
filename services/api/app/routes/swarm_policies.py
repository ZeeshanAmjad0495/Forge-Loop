import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    SwarmBudgetCheckRequest,
    SwarmBudgetCheckResponse,
    SwarmPolicy,
    SwarmPolicyCreate,
    SwarmPolicyUpdate,
)
from ..repositories_state import (
    budget_policy_repo,
    cost_record_repo,
    project_repo,
    swarm_policy_repo,
)
from ..services.swarm_budget import check_swarm_budget

router = APIRouter()


@router.post(
    "/projects/{project_id}/swarm-policies",
    response_model=SwarmPolicy,
    status_code=201,
)
def create_swarm_policy(
    project_id: str,
    body: SwarmPolicyCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    policy = SwarmPolicy(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=body.name,
        enabled=body.enabled,
        swarm_type=body.swarm_type,
        max_agents=body.max_agents,
        max_tool_calls=body.max_tool_calls,
        max_estimated_cost_usd=body.max_estimated_cost_usd,
        max_context_tokens_per_agent=body.max_context_tokens_per_agent,
        allowed_providers=list(body.allowed_providers),
        requires_approval=body.requires_approval,
        default_model_route=body.default_model_route,
        created_at=now,
        updated_at=now,
    )
    swarm_policy_repo.save(policy)
    return policy


@router.get(
    "/projects/{project_id}/swarm-policies",
    response_model=list[SwarmPolicy],
)
def list_swarm_policies(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return swarm_policy_repo.list_by_project(project_id)


@router.get(
    "/swarm-policies/{swarm_policy_id}",
    response_model=SwarmPolicy,
)
def get_swarm_policy(
    swarm_policy_id: str,
    current_user: str = Depends(require_auth),
):
    policy = swarm_policy_repo.get(swarm_policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Swarm policy not found")
    return policy


@router.patch(
    "/swarm-policies/{swarm_policy_id}",
    response_model=SwarmPolicy,
)
def update_swarm_policy(
    swarm_policy_id: str,
    body: SwarmPolicyUpdate,
    current_user: str = Depends(require_auth),
):
    policy = swarm_policy_repo.get(swarm_policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Swarm policy not found")
    data = policy.model_dump()
    for field, value in body.model_dump(exclude_unset=True).items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = SwarmPolicy(**data)
    swarm_policy_repo.update(updated)
    return updated


@router.post(
    "/projects/{project_id}/swarm-budget-check",
    response_model=SwarmBudgetCheckResponse,
)
def project_swarm_budget_check(
    project_id: str,
    body: SwarmBudgetCheckRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_swarm_budget(
        swarm_policy_repo,
        budget_policy_repo,
        cost_record_repo,
        project_id=project_id,
        request=body,
    )
