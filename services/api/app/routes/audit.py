from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import AuditEvent
from ..repositories_state import audit_event_repo, project_repo

router = APIRouter()


@router.get("/projects/{project_id}/audit-events", response_model=list[AuditEvent])
def list_project_audit_events(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return audit_event_repo.list_by_project(project_id)


@router.get("/audit-events/{audit_event_id}", response_model=AuditEvent)
def get_audit_event(audit_event_id: str, _: str = Depends(require_auth)):
    event = audit_event_repo.get(audit_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="AuditEvent not found")
    return event
