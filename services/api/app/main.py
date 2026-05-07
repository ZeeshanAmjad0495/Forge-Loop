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
from .lifecycle import LifecycleError, compute_readiness, validate_transition
from .models import (
    DevTaskUpdate,
    DevTaskWithReadiness,
    DevTaskWithSubtasksResponse,
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
    Requirement,
    RequirementAnalysis,
    RequirementAnalysisRunCreate,
    RequirementAnalysisRunResponse,
    RequirementCreate,
    RequirementUpdate,
    SubtaskUpdate,
    TaskDecompositionResponse,
    TaskDecompositionRunCreate,
    Ticket,
    TicketCreate,
)
from .planning_agent import run_planning_agent
from .repositories import get_repositories
from .requirement_analysis_agent import (
    run_requirement_analysis_agent,
    run_requirement_analysis_for_requirement,
)
from .task_decomposition_agent import (
    run_task_decomposition_for_requirement,
    run_task_decomposition_for_ticket,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
(
    repo,
    agent_run_repo,
    artifact_repo,
    project_repo,
    project_context_repo,
    analysis_repo,
    requirement_repo,
    dev_task_repo,
    subtask_repo,
) = get_repositories()


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


@app.post(
    "/tickets/{ticket_id}/requirement-analyses",
    response_model=RequirementAnalysisRunResponse,
    status_code=201,
)
def create_requirement_analysis(
    ticket_id: str,
    body: RequirementAnalysisRunCreate | None = Body(default=None),
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
    run, analysis, artifact = run_requirement_analysis_agent(
        ticket, provider, agent_run_repo, artifact_repo, analysis_repo, context
    )
    return RequirementAnalysisRunResponse(agent_run=run, requirement_analysis=analysis, artifact=artifact)


@app.get("/tickets/{ticket_id}/requirement-analyses", response_model=list[RequirementAnalysis])
def list_requirement_analyses(ticket_id: str, _: str = Depends(require_auth)):
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return analysis_repo.list_by_ticket(ticket_id)


@app.get("/llm/providers", response_model=ProvidersResponse)
def get_providers(_: str = Depends(require_auth)):
    return ProvidersResponse(
        default_provider=get_default_provider_name(),
        providers=[ProviderInfo(**p) for p in list_provider_status()],
    )


# ---------------------------------------------------------------------------
# Structured requirements
# ---------------------------------------------------------------------------

@app.post("/projects/{project_id}/requirements", response_model=Requirement, status_code=201)
def create_project_requirement(
    project_id: str,
    body: RequirementCreate,
    _: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    requirement = Requirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=body.title,
        problem_statement=body.problem_statement,
        business_goal=body.business_goal,
        target_users=body.target_users,
        functional_requirements=body.functional_requirements,
        non_functional_requirements=body.non_functional_requirements,
        acceptance_criteria=body.acceptance_criteria,
        constraints=body.constraints,
        non_goals=body.non_goals,
        assumptions=body.assumptions,
        source=body.source,
        status=body.status,
        created_at=now,
        updated_at=now,
    )
    requirement_repo.save(requirement)
    return requirement


@app.get("/projects/{project_id}/requirements", response_model=list[Requirement])
def list_project_requirements(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return requirement_repo.list_by_project(project_id)


@app.get("/requirements/{requirement_id}", response_model=Requirement)
def get_requirement(requirement_id: str, _: str = Depends(require_auth)):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@app.put("/requirements/{requirement_id}", response_model=Requirement)
def update_requirement(
    requirement_id: str,
    body: RequirementUpdate,
    _: str = Depends(require_auth),
):
    existing = requirement_repo.get(requirement_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    updated = existing.model_copy(
        update={
            "title": body.title,
            "problem_statement": body.problem_statement,
            "business_goal": body.business_goal,
            "target_users": body.target_users,
            "functional_requirements": body.functional_requirements,
            "non_functional_requirements": body.non_functional_requirements,
            "acceptance_criteria": body.acceptance_criteria,
            "constraints": body.constraints,
            "non_goals": body.non_goals,
            "assumptions": body.assumptions,
            "status": body.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    requirement_repo.update(updated)
    return updated


@app.post(
    "/requirements/{requirement_id}/requirement-analyses",
    response_model=RequirementAnalysisRunResponse,
    status_code=201,
)
def create_requirement_analysis_for_requirement(
    requirement_id: str,
    body: RequirementAnalysisRunCreate | None = Body(default=None),
    _: str = Depends(require_auth),
):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    context = project_context_repo.get(requirement.project_id)
    run, analysis, artifact = run_requirement_analysis_for_requirement(
        requirement, provider, agent_run_repo, artifact_repo, analysis_repo, context
    )
    updated = requirement.model_copy(
        update={"status": "analyzed", "updated_at": datetime.now(timezone.utc)}
    )
    requirement_repo.update(updated)
    return RequirementAnalysisRunResponse(
        agent_run=run, requirement_analysis=analysis, artifact=artifact
    )


# ---------------------------------------------------------------------------
# Task decomposition
# ---------------------------------------------------------------------------

@app.post(
    "/requirements/{requirement_id}/task-decompositions",
    response_model=TaskDecompositionResponse,
    status_code=201,
)
def create_task_decomposition_for_requirement(
    requirement_id: str,
    body: TaskDecompositionRunCreate | None = Body(default=None),
    _: str = Depends(require_auth),
):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    context = project_context_repo.get(requirement.project_id)
    latest_analysis = analysis_repo.get_latest_by_requirement(requirement_id)
    run, artifact, dev_tasks, subtasks = run_task_decomposition_for_requirement(
        requirement, provider, agent_run_repo, artifact_repo, dev_task_repo, subtask_repo,
        context, latest_analysis,
    )
    return TaskDecompositionResponse(
        agent_run=run, artifact=artifact, dev_tasks=dev_tasks, subtasks=subtasks
    )


@app.post(
    "/tickets/{ticket_id}/task-decompositions",
    response_model=TaskDecompositionResponse,
    status_code=201,
)
def create_task_decomposition_for_ticket(
    ticket_id: str,
    body: TaskDecompositionRunCreate | None = Body(default=None),
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
    latest_analysis = analysis_repo.get_latest_by_ticket(ticket_id)
    run, artifact, dev_tasks, subtasks = run_task_decomposition_for_ticket(
        ticket, provider, agent_run_repo, artifact_repo, dev_task_repo, subtask_repo,
        context, latest_analysis,
    )
    return TaskDecompositionResponse(
        agent_run=run, artifact=artifact, dev_tasks=dev_tasks, subtasks=subtasks
    )


def _with_readiness(dev_task) -> DevTaskWithReadiness:
    is_ready, blocked_by = compute_readiness(dev_task, dev_task_repo.get)
    return DevTaskWithReadiness(**dev_task.model_dump(), is_ready=is_ready, blocked_by=blocked_by)


@app.get("/projects/{project_id}/dev-tasks", response_model=list[DevTaskWithReadiness])
def list_project_dev_tasks(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return [_with_readiness(t) for t in dev_task_repo.list_by_project(project_id)]


@app.get("/dev-tasks/{dev_task_id}", response_model=DevTaskWithSubtasksResponse)
def get_dev_task(dev_task_id: str, _: str = Depends(require_auth)):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    subtasks = subtask_repo.list_by_dev_task(dev_task_id)
    return DevTaskWithSubtasksResponse(dev_task=_with_readiness(dev_task), subtasks=subtasks)


@app.patch("/dev-tasks/{dev_task_id}", response_model=DevTaskWithReadiness)
def update_dev_task(
    dev_task_id: str,
    body: DevTaskUpdate,
    _: str = Depends(require_auth),
):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    try:
        if new_status and new_status != dev_task.status:
            validate_transition(dev_task.status, new_status)
            if new_status in ("ready", "in_progress"):
                candidate = dev_task.model_copy(update=patch)
                blockers = compute_readiness(candidate, dev_task_repo.get)[1]
                if blockers:
                    raise LifecycleError(
                        f"Cannot move to {new_status}: dependencies not completed: {blockers}"
                    )
    except LifecycleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    updated = dev_task.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    dev_task_repo.update(updated)
    return _with_readiness(updated)


@app.patch("/subtasks/{subtask_id}")
def update_subtask(
    subtask_id: str,
    body: SubtaskUpdate,
    _: str = Depends(require_auth),
):
    subtask = subtask_repo.get(subtask_id)
    if subtask is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    if new_status and new_status != subtask.status:
        try:
            validate_transition(subtask.status, new_status)
        except LifecycleError as e:
            raise HTTPException(status_code=400, detail=str(e))
    updated = subtask.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    subtask_repo.update(updated)
    return updated


@app.get("/dev-tasks/{dev_task_id}/subtasks", response_model=list)
def list_dev_task_subtasks(dev_task_id: str, _: str = Depends(require_auth)):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return subtask_repo.list_by_dev_task(dev_task_id)
