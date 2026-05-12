from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    WorkSafeCheckRequest,
    WorkSafeCheckResponse,
    WorkSafePolicy,
    WorkSafePolicyCreate,
    WorkSafePolicyUpdate,
)
from ..repositories_state import (
    audit_writer,
    project_repo,
    work_safe_policy_repo,
)
from ..services.work_safe_policies import (
    archive_policy,
    check_action,
    create_policy,
    effective_policy,
    update_policy,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _get_or_404(policy_id: str) -> WorkSafePolicy:
    policy = work_safe_policy_repo.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Work-safe policy not found")
    return policy


@router.post("/work-safe-policies", response_model=WorkSafePolicy, status_code=201)
def create_work_safe_policy(
    body: WorkSafePolicyCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    policy = create_policy(work_safe_policy_repo, body=body)
    audit_writer.write(
        action="work_safe_policy_created",
        target_type="work_safe_policy",
        target_id=policy.id,
        project_id=policy.project_id,
        actor_email=current_user,
        details={"policy_level": policy.policy_level, "status": policy.status},
    )
    return policy


@router.get("/work-safe-policies", response_model=list[WorkSafePolicy])
def list_work_safe_policies(
    project_id: str | None = None,
    status: str | None = None,
    policy_level: str | None = None,
    current_user: str = Depends(require_auth),
):
    if project_id is not None:
        _ensure_project(project_id)
        items = work_safe_policy_repo.list_by_project(project_id)
    else:
        items = work_safe_policy_repo.list_all()
    if status is not None:
        items = [p for p in items if p.status == status]
    if policy_level is not None:
        items = [p for p in items if p.policy_level == policy_level]
    return items


@router.get(
    "/projects/{project_id}/work-safe-policies",
    response_model=list[WorkSafePolicy],
)
def list_project_work_safe_policies(
    project_id: str,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = work_safe_policy_repo.list_by_project(project_id)
    if status is not None:
        items = [p for p in items if p.status == status]
    return items


@router.get(
    "/projects/{project_id}/work-safe-policy/effective",
    response_model=WorkSafePolicy | None,
)
def get_effective_policy(
    project_id: str, current_user: str = Depends(require_auth)
):
    _ensure_project(project_id)
    return effective_policy(work_safe_policy_repo, project_id)


@router.post(
    "/projects/{project_id}/work-safe-policy/check",
    response_model=WorkSafeCheckResponse,
)
def check_project_action(
    project_id: str,
    body: WorkSafeCheckRequest,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    policy = effective_policy(work_safe_policy_repo, project_id)
    response = check_action(policy, body)
    audit_writer.write(
        action="work_safe_action_checked",
        target_type="work_safe_policy",
        target_id=response.policy_id or "no-policy",
        project_id=project_id,
        actor_email=current_user,
        details={
            "action": response.action,
            "decision": response.decision,
        },
    )
    return response


@router.get("/work-safe-policies/{policy_id}", response_model=WorkSafePolicy)
def get_work_safe_policy(
    policy_id: str, current_user: str = Depends(require_auth)
):
    return _get_or_404(policy_id)


@router.patch("/work-safe-policies/{policy_id}", response_model=WorkSafePolicy)
def patch_work_safe_policy(
    policy_id: str,
    body: WorkSafePolicyUpdate,
    current_user: str = Depends(require_auth),
):
    policy = _get_or_404(policy_id)
    updated = update_policy(work_safe_policy_repo, policy, body)
    audit_writer.write(
        action="work_safe_policy_updated",
        target_type="work_safe_policy",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/work-safe-policies/{policy_id}/archive", response_model=WorkSafePolicy
)
def archive_work_safe_policy(
    policy_id: str, current_user: str = Depends(require_auth)
):
    policy = _get_or_404(policy_id)
    archived = archive_policy(work_safe_policy_repo, policy)
    audit_writer.write(
        action="work_safe_policy_archived",
        target_type="work_safe_policy",
        target_id=archived.id,
        project_id=archived.project_id,
        actor_email=current_user,
    )
    return archived
