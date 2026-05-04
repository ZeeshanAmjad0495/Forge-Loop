import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .llm import get_provider
from .models import PlanningRunResponse, Ticket, TicketCreate
from .planning_agent import run_planning_agent
from .repositories import get_repositories

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
repo, agent_run_repo, artifact_repo = get_repositories()
llm_provider = get_provider()


@app.get("/health")
def health():
    return {"status": "ok", "service": "incidentpilot-api"}


@app.post("/tickets", response_model=Ticket, status_code=201)
def create_ticket(body: TicketCreate):
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


@app.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/tickets/{ticket_id}/planning-runs", response_model=PlanningRunResponse, status_code=201)
def create_planning_run(ticket_id: str):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    run, artifact = run_planning_agent(ticket, llm_provider, agent_run_repo, artifact_repo)
    updated = ticket.model_copy(update={"status": "brief_generated", "updated_at": datetime.now(timezone.utc)})
    repo.save(updated)
    return PlanningRunResponse(agent_run=run, artifact=artifact)


@app.get("/tickets/{ticket_id}/artifacts")
def list_artifacts(ticket_id: str):
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return artifact_repo.list_by_ticket(ticket_id)
