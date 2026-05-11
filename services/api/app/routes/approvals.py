import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import Approval, ApprovalCreate, ApprovalUpdate, AuditAction
from ..repositories_state import approval_repo, audit_writer, project_repo

router = APIRouter()

_FINAL_APPROVAL_STATUSES = {"approved", "rejected", "needs_revision"}


@router.post("/approvals", response_model=Approval, status_code=201)
def create_approval(
    body: ApprovalCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    approval = Approval(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        target_type=body.target_type,
        target_id=body.target_id,
        status="pending",
        requested_by=current_user,
        feedback=body.feedback,
        created_at=now,
        updated_at=now,
    )
    approval_repo.save(approval)
    audit_writer.write(
        "approval_requested", "approval", approval.id,
        project_id=body.project_id, actor_email=current_user,
        details={"target_type": body.target_type, "target_id": body.target_id},
    )
    return approval


@router.get("/projects/{project_id}/approvals", response_model=list[Approval])
def list_project_approvals(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return approval_repo.list_by_project(project_id)


@router.get("/approvals/{approval_id}", response_model=Approval)
def get_approval(approval_id: str, _: str = Depends(require_auth)):
    approval = approval_repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.patch("/approvals/{approval_id}", response_model=Approval)
def decide_approval(
    approval_id: str,
    body: ApprovalUpdate,
    current_user: str = Depends(require_auth),
):
    approval = approval_repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if body.status not in _FINAL_APPROVAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid approval status: {body.status!r}")
    if approval.status in _FINAL_APPROVAL_STATUSES and body.status != approval.status:
        raise HTTPException(status_code=400, detail="approval already finalized")
    now = datetime.now(timezone.utc)
    updated = approval.model_copy(
        update={
            "status": body.status,
            "feedback": body.feedback if body.feedback is not None else approval.feedback,
            "decided_by": current_user,
            "decided_at": now,
            "updated_at": now,
        }
    )
    approval_repo.update(updated)
    action: AuditAction = f"approval_{body.status}"  # type: ignore[assignment]
    audit_writer.write(
        action, "approval", approval.id,
        project_id=approval.project_id, actor_email=current_user,
        details={"feedback": body.feedback} if body.feedback else {},
    )
    return updated
