import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import create_access_token, require_auth, verify_credentials
from .llm import (
    ProviderError,
    get_default_provider_name,
    get_provider_by_name,
    list_provider_status,
)
from .models import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    PlanningRunCreate,
    PlanningRunResponse,
    Project,
    ProjectContext,
    ProjectContextUpdate,
    ProjectCreate,
    ProviderInfo,
    ProvidersResponse,
    Ticket,
    TicketCreate,
)
from .planning_agent import run_planning_agent
from .repositories import get_repositories

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
repo, agent_run_repo, artifact_repo, project_repo, project_context_repo = get_repositories()


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "incidentpilot-api"}


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if not verify_credentials(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        token = create_access_token(body.email)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Auth misconfigured")
    return LoginResponse(access_token=token)


# ---------------------------------------------------------------------------
# Protected endpoints
# ---------------------------------------------------------------------------

@app.get("/auth/me", response_model=MeResponse)
def me(current_user: str = Depends(require_auth)):
    return MeResponse(email=current_user)


@app.post("/projects", response_model=Project, status_code=201)
def create_project(body: ProjectCreate, _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc)
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        repo_url=body.repo_url,
        tech_stack=body.tech_stack,
        status="active",
        created_at=now,
        updated_at=now,
    )
    project_repo.save(project)
    return project


@app.get("/projects", response_model=list[Project])
def list_projects(_: str = Depends(require_auth)):
    return project_repo.list_all()


@app.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, _: str = Depends(require_auth)):
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.get("/projects/{project_id}/context", response_model=ProjectContext)
def get_project_context(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ctx = project_context_repo.get(project_id)
    if ctx is None:
        return ProjectContext(project_id=project_id)
    return ctx


@app.put("/projects/{project_id}/context", response_model=ProjectContext)
def update_project_context(
    project_id: str,
    body: ProjectContextUpdate,
    _: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ctx = ProjectContext(
        project_id=project_id,
        architecture_notes=body.architecture_notes,
        coding_standards=body.coding_standards,
        test_commands=body.test_commands,
        deployment_commands=body.deployment_commands,
        domain_rules=body.domain_rules,
        safety_rules=body.safety_rules,
        updated_at=datetime.now(timezone.utc),
    )
    project_context_repo.save(ctx)
    return ctx


@app.post("/projects/{project_id}/tickets", response_model=Ticket, status_code=201)
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


@app.get("/projects/{project_id}/tickets", response_model=list[Ticket])
def list_project_tickets(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.list_by_project(project_id)


@app.post("/tickets", response_model=Ticket, status_code=201)
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


@app.get("/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str, _: str = Depends(require_auth)):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/tickets/{ticket_id}/planning-runs", response_model=PlanningRunResponse, status_code=201)
def create_planning_run(
    ticket_id: str,
    body: PlanningRunCreate | None = Body(default=None),
    _: str = Depends(require_auth),
):
    ticket = repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    context = None
    if ticket.project_id:
        context = project_context_repo.get(ticket.project_id)
    run, artifact = run_planning_agent(ticket, provider, agent_run_repo, artifact_repo, context)
    updated = ticket.model_copy(update={"status": "brief_generated", "updated_at": datetime.now(timezone.utc)})
    repo.save(updated)
    return PlanningRunResponse(agent_run=run, artifact=artifact)


@app.get("/tickets/{ticket_id}/artifacts")
def list_artifacts(ticket_id: str, _: str = Depends(require_auth)):
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return artifact_repo.list_by_ticket(ticket_id)


@app.get("/llm/providers", response_model=ProvidersResponse)
def get_providers(_: str = Depends(require_auth)):
    return ProvidersResponse(
        default_provider=get_default_provider_name(),
        providers=[ProviderInfo(**p) for p in list_provider_status()],
    )
