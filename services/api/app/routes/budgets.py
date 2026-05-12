import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_auth
from ..models import (
    BudgetCheckRequest,
    BudgetPolicy,
    BudgetPolicyCreate,
    BudgetPolicyUpdate,
    BudgetStatus,
)
from ..repositories_state import budget_policy_repo, cost_record_repo, project_repo
from ..services.budget_controls import get_budget_status

router = APIRouter()


@router.post(
    "/projects/{project_id}/budget-policies",
    response_model=BudgetPolicy,
    status_code=201,
)
def create_budget_policy(
    project_id: str,
    body: BudgetPolicyCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    policy = BudgetPolicy(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=body.name,
        enabled=body.enabled,
        currency=body.currency,
        period=body.period,
        warning_limit_usd=body.warning_limit_usd,
        hard_limit_usd=body.hard_limit_usd,
        per_run_limit_usd=body.per_run_limit_usd,
        workflow_type=body.workflow_type,
        provider=body.provider,
        model=body.model,
        created_at=now,
        updated_at=now,
    )
    budget_policy_repo.save(policy)
    return policy


@router.get(
    "/projects/{project_id}/budget-policies",
    response_model=list[BudgetPolicy],
)
def list_budget_policies(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return budget_policy_repo.list_by_project(project_id)


@router.get(
    "/budget-policies/{budget_policy_id}",
    response_model=BudgetPolicy,
)
def get_budget_policy(
    budget_policy_id: str,
    current_user: str = Depends(require_auth),
):
    policy = budget_policy_repo.get(budget_policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Budget policy not found")
    return policy


@router.patch(
    "/budget-policies/{budget_policy_id}",
    response_model=BudgetPolicy,
)
def update_budget_policy(
    budget_policy_id: str,
    body: BudgetPolicyUpdate,
    current_user: str = Depends(require_auth),
):
    policy = budget_policy_repo.get(budget_policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Budget policy not found")
    data = policy.model_dump()
    for field, value in body.model_dump(exclude_unset=True).items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = BudgetPolicy(**data)
    budget_policy_repo.update(updated)
    return updated


@router.get(
    "/projects/{project_id}/budget-status",
    response_model=BudgetStatus,
)
def project_budget_status(
    project_id: str,
    workflow_type: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_budget_status(
        budget_policy_repo,
        cost_record_repo,
        project_id=project_id,
        workflow_type=workflow_type,
        provider=provider,
        model=model,
    )


@router.post(
    "/projects/{project_id}/budget-check",
    response_model=BudgetStatus,
)
def project_budget_check(
    project_id: str,
    body: BudgetCheckRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_budget_status(
        budget_policy_repo,
        cost_record_repo,
        project_id=project_id,
        workflow_type=body.workflow_type,
        provider=body.provider,
        model=body.model,
        estimated_cost_usd=body.estimated_cost_usd,
    )
