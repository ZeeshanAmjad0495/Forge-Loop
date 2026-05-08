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
    Approval,
    ApprovalCreate,
    ApprovalUpdate,
    AuditAction,
    AuditEvent,
    CodeRepository,
    CodeRepositoryCreate,
    CodeRepositoryUpdate,
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
    RequirementGenerationResponse,
    RequirementGenerationRunCreate,
    RequirementUpdate,
    RepoSafetyProfile,
    RepoSafetyProfileUpsert,
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
from .requirement_generation_agent import run_requirement_generation_agent
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
    approval_repo,
    audit_event_repo,
    code_repo_repo,
    repo_safety_profile_repo,
) = get_repositories()

# ---------------------------------------------------------------------------
# Default safety profile constants
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_ACTIONS = ["read_code", "run_tests", "propose_changes"]
DEFAULT_BLOCKED_PATHS = [
    ".env",
    ".env.*",
    "secrets/",
    "credentials/",
    "terraform.tfstate",
    "infra/prod/",
]
DEFAULT_REQUIRED_CHECKS = ["tests", "build"]
DEFAULT_REQUIRES_APPROVAL_FOR = [
    "create_branch",
    "create_pr",
    "modify_infra",
    "update_dependencies",
    "delete_files",
    "deployment",
]
DEFAULT_PROTECTED_BRANCHES = ["main", "master"]
DEFAULT_WORK_SAFE_MODE = True


def _default_safety_profile(repo_id: str, project_id: str) -> RepoSafetyProfile:
    now = datetime.now(timezone.utc)
    return RepoSafetyProfile(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=repo_id,
        work_safe_mode=DEFAULT_WORK_SAFE_MODE,
        allowed_actions=list(DEFAULT_ALLOWED_ACTIONS),
        blocked_paths=list(DEFAULT_BLOCKED_PATHS),
        required_checks=list(DEFAULT_REQUIRED_CHECKS),
        requires_approval_for=list(DEFAULT_REQUIRES_APPROVAL_FOR),
        protected_branches=list(DEFAULT_PROTECTED_BRANCHES),
        notes="",
        created_at=now,
        updated_at=now,
    )


def _audit(
    action: AuditAction,
    target_type: str,
    target_id: str,
    project_id: str | None = None,
    actor_email: str | None = None,
    details: dict | None = None,
) -> None:
    actor_type = "user" if (actor_email and actor_email != "auth-disabled") else "system"
    event = AuditEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        actor_type=actor_type,
        actor_id=actor_email or "system",
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        created_at=datetime.now(timezone.utc),
    )
    audit_event_repo.save(event)


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
    current_user: str = Depends(require_auth),
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
    _audit(
        "requirement_created", "requirement", requirement.id,
        project_id=project_id, actor_email=current_user,
    )
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
    "/projects/{project_id}/requirement-generations",
    response_model=RequirementGenerationResponse,
    status_code=201,
)
def create_project_requirement_generation(
    project_id: str,
    body: RequirementGenerationRunCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    context = project_context_repo.get(project_id)
    code_repos = code_repo_repo.list_by_project(project_id)
    code_repository = code_repos[0] if code_repos else None
    safety_profile = (
        repo_safety_profile_repo.get_by_repo(code_repository.id)
        if code_repository is not None
        else None
    )
    run, requirements, artifact = run_requirement_generation_agent(
        project,
        provider,
        agent_run_repo,
        artifact_repo,
        requirement_repo,
        context,
        code_repository,
        safety_profile,
    )
    _audit(
        "requirement_generation_created", "agent_run", run.id,
        project_id=project_id, actor_email=current_user,
        details={
            "requirement_count": len(requirements),
            "provider": provider.provider_name,
        },
    )
    for requirement in requirements:
        _audit(
            "requirement_created", "requirement", requirement.id,
            project_id=project_id, actor_email=current_user,
            details={"source": "agent_generated"},
        )
    return RequirementGenerationResponse(
        agent_run=run, artifact=artifact, requirements=requirements,
    )


@app.post(
    "/requirements/{requirement_id}/requirement-analyses",
    response_model=RequirementAnalysisRunResponse,
    status_code=201,
)
def create_requirement_analysis_for_requirement(
    requirement_id: str,
    body: RequirementAnalysisRunCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
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
    _audit(
        "requirement_analyzed", "requirement_analysis", analysis.id,
        project_id=requirement.project_id, actor_email=current_user,
        details={"requirement_id": requirement_id},
    )
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
    current_user: str = Depends(require_auth),
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
    _audit(
        "task_decomposition_created", "task_decomposition", run.id,
        project_id=requirement.project_id, actor_email=current_user,
        details={"dev_task_count": len(dev_tasks)},
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
    current_user: str = Depends(require_auth),
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
    _audit(
        "task_decomposition_created", "task_decomposition", run.id,
        project_id=ticket.project_id, actor_email=current_user,
        details={"dev_task_count": len(dev_tasks)},
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
    current_user: str = Depends(require_auth),
):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    old_status = dev_task.status
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
            if dev_task.status == "proposed" and new_status == "ready":
                approved = (
                    approval_repo.find_approved_for_target("dev_task", dev_task.id)
                    or approval_repo.find_approved_for_target("task_decomposition", dev_task.agent_run_id)
                )
                if approved is None:
                    raise HTTPException(
                        status_code=400,
                        detail="DevTask requires an approved approval before moving to ready",
                    )
    except LifecycleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    updated = dev_task.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    dev_task_repo.update(updated)
    if new_status and new_status != old_status:
        _audit(
            "dev_task_updated", "dev_task", dev_task.id,
            project_id=dev_task.project_id, actor_email=current_user,
            details={"from": old_status, "to": new_status},
        )
    return _with_readiness(updated)


@app.patch("/subtasks/{subtask_id}")
def update_subtask(
    subtask_id: str,
    body: SubtaskUpdate,
    current_user: str = Depends(require_auth),
):
    subtask = subtask_repo.get(subtask_id)
    if subtask is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    old_status = subtask.status
    if new_status and new_status != subtask.status:
        try:
            validate_transition(subtask.status, new_status)
        except LifecycleError as e:
            raise HTTPException(status_code=400, detail=str(e))
    updated = subtask.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    subtask_repo.update(updated)
    if new_status and new_status != old_status:
        _audit(
            "subtask_updated", "subtask", subtask.id,
            project_id=subtask.project_id, actor_email=current_user,
            details={"from": old_status, "to": new_status},
        )
    return updated


@app.get("/dev-tasks/{dev_task_id}/subtasks", response_model=list)
def list_dev_task_subtasks(dev_task_id: str, _: str = Depends(require_auth)):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return subtask_repo.list_by_dev_task(dev_task_id)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

_FINAL_APPROVAL_STATUSES = {"approved", "rejected", "needs_revision"}


@app.post("/approvals", response_model=Approval, status_code=201)
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
    _audit(
        "approval_requested", "approval", approval.id,
        project_id=body.project_id, actor_email=current_user,
        details={"target_type": body.target_type, "target_id": body.target_id},
    )
    return approval


@app.get("/projects/{project_id}/approvals", response_model=list[Approval])
def list_project_approvals(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return approval_repo.list_by_project(project_id)


@app.get("/approvals/{approval_id}", response_model=Approval)
def get_approval(approval_id: str, _: str = Depends(require_auth)):
    approval = approval_repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@app.patch("/approvals/{approval_id}", response_model=Approval)
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
    _audit(
        action, "approval", approval.id,
        project_id=approval.project_id, actor_email=current_user,
        details={"feedback": body.feedback} if body.feedback else {},
    )
    return updated


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/audit-events", response_model=list[AuditEvent])
def list_project_audit_events(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return audit_event_repo.list_by_project(project_id)


@app.get("/audit-events/{audit_event_id}", response_model=AuditEvent)
def get_audit_event(audit_event_id: str, _: str = Depends(require_auth)):
    event = audit_event_repo.get(audit_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="AuditEvent not found")
    return event


# ---------------------------------------------------------------------------
# Code repositories
# ---------------------------------------------------------------------------

@app.post("/projects/{project_id}/code-repositories", response_model=CodeRepository, status_code=201)
def create_code_repository(
    project_id: str,
    body: CodeRepositoryCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    repo_obj = CodeRepository(
        id=str(uuid.uuid4()),
        project_id=project_id,
        provider=body.provider,
        repo_url=body.repo_url,
        name=body.name,
        default_branch=body.default_branch,
        status="active",
        created_at=now,
        updated_at=now,
    )
    code_repo_repo.save(repo_obj)
    _audit(
        "code_repository_created",
        "code_repository",
        repo_obj.id,
        project_id=project_id,
        actor_email=current_user,
        details={"provider": repo_obj.provider, "repo_url": repo_obj.repo_url},
    )
    return repo_obj


@app.get("/projects/{project_id}/code-repositories", response_model=list[CodeRepository])
def list_project_code_repositories(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return code_repo_repo.list_by_project(project_id)


@app.get("/code-repositories/{repo_id}", response_model=CodeRepository)
def get_code_repository(repo_id: str, _: str = Depends(require_auth)):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    return repo_obj


@app.patch("/code-repositories/{repo_id}", response_model=CodeRepository)
def update_code_repository(
    repo_id: str,
    body: CodeRepositoryUpdate,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    changed_fields = [k for k, v in body.model_dump(exclude_unset=True).items() if v is not None]
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc)
    updated = repo_obj.model_copy(update=updates)
    code_repo_repo.update(updated)
    _audit(
        "code_repository_updated",
        "code_repository",
        repo_obj.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"changed_fields": changed_fields},
    )
    return updated


# ---------------------------------------------------------------------------
# Repo safety profiles
# ---------------------------------------------------------------------------

@app.post("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def upsert_repo_safety_profile(
    repo_id: str,
    body: RepoSafetyProfileUpsert,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    now = datetime.now(timezone.utc)
    profile_id = existing.id if existing else str(uuid.uuid4())
    created_at = existing.created_at if existing else now
    status_code = 200 if existing else 201
    profile = RepoSafetyProfile(
        id=profile_id,
        project_id=repo_obj.project_id,
        code_repository_id=repo_id,
        work_safe_mode=body.work_safe_mode,
        allowed_actions=body.allowed_actions,
        blocked_paths=body.blocked_paths,
        required_checks=body.required_checks,
        requires_approval_for=body.requires_approval_for,
        protected_branches=body.protected_branches,
        notes=body.notes,
        created_at=created_at,
        updated_at=now,
    )
    repo_safety_profile_repo.save(profile)
    _audit(
        "repo_safety_profile_updated",
        "repo_safety_profile",
        profile.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"code_repository_id": repo_id},
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(content=profile.model_dump(mode="json"), status_code=status_code)


@app.get("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def get_repo_safety_profile(repo_id: str, _: str = Depends(require_auth)):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    if existing:
        return existing
    return _default_safety_profile(repo_id, repo_obj.project_id)


@app.patch("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def patch_repo_safety_profile(
    repo_id: str,
    body: RepoSafetyProfileUpsert,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    base = existing if existing else _default_safety_profile(repo_id, repo_obj.project_id)
    now = datetime.now(timezone.utc)
    patch_data = body.model_dump(exclude_unset=True)
    updated = base.model_copy(update={**patch_data, "updated_at": now})
    if not existing:
        updated = updated.model_copy(update={"created_at": now})
    repo_safety_profile_repo.save(updated)
    _audit(
        "repo_safety_profile_updated",
        "repo_safety_profile",
        updated.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"code_repository_id": repo_id},
    )
    return updated
