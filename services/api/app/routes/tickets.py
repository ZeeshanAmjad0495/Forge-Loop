import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import Ticket, TicketCreate
from ..repositories_state import artifact_repo, project_repo, repo

router = APIRouter()


@router.post("/projects/{project_id}/tickets", response_model=Ticket, status_code=201)
def create_project_ticket(
    project_id: str,
    body: TicketCreate,
    _: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        status="created",
        created_at=now,
        updated_at=now,
        project_id=project_id,
    )
    repo.save(ticket)
    return ticket


@router.get("/projects/{project_id}/tickets", response_model=list[Ticket])
def list_project_tickets(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.list_by_project(project_id)


@router.post("/tickets", response_model=Ticket, status_code=201)
def create_ticket(body: TicketCreate, _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        status="created",
        created_at=now,
        updated_at=now,
    )
    repo.save(ticket)
    return ticket


@router.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str, _: str = Depends(require_auth)):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/tickets/{ticket_id}/artifacts")
def list_artifacts(ticket_id: str, _: str = Depends(require_auth)):
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return artifact_repo.list_by_ticket(ticket_id)
