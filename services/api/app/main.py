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
    CheckDefinition,
    CheckDefinitionCreate,
    CheckDefinitionUpdate,
    CheckDefinitionsFromSafetyProfileRequest,
    CheckDefinitionsFromSafetyProfileResponse,
    CheckRun,
    CheckRunCreate,
    CheckType,
    CIAnalysis,
    CIAnalysisCreate,
    CIEvent,
    CIEventCreate,
    CodeRepository,
    CodeRepositoryCreate,
    CodeRepositoryUpdate,
    DevTaskUpdate,
    DevTaskWithReadiness,
    DevTaskWithSubtasksResponse,
    Epic,
    EpicCreate,
    EpicUpdate,
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
    RunnerType,
    SubtaskUpdate,
    TaskDecompositionResponse,
    TaskDecompositionRunCreate,
    Ticket,
    TicketCreate,
    ToolRun,
    ToolRunCreate,
    ToolRunnerDefinition,
    ToolRunnerDefinitionCreate,
    ToolRunnerDefinitionUpdate,
    ToolRunnerDefinitionsDefaultsRequest,
    ToolRunnerDefinitionsDefaultsResponse,
    OpenHandsPreparePackageRequest,
    OpenHandsInstructionPackage,
    OpenHandsPrepareResponse,
    OpenHandsRecordResultRequest,
    PullRequestDraft,
    PullRequestDraftCreate,
    PullRequestDraftUpdate,
    PullRequestReview,
    PullRequestReviewComplete,
    PullRequestReviewCreate,
    PullRequestReviewUpdate,
)
from .pr_draft import (
    build_pr_draft_content,
    derive_source_branch,
    is_allowed_status_transition,
)
from .pr_review.kody import (
    KodyReviewAdapter,
    build_kody_review_package,
    is_allowed_review_status_transition,
)
from .tool_runners.openhands import OpenHandsRunner
from .ci_analysis.agent import run_ci_failure_analysis
import json

from . import config as _config
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
    epic_repo,
    check_definition_repo,
    check_run_repo,
    tool_runner_definition_repo,
    tool_run_repo,
    pr_draft_repo,
    pr_review_repo,
    ci_event_repo,
    ci_analysis_repo,
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


# ---------------------------------------------------------------------------
# Check definition mapping (Task 25)
# ---------------------------------------------------------------------------

# Maps a required_checks string value to (check_type, default_name, default_command).
# Unknown keys are silently skipped so free-form safety profile values don't 400.
_CHECK_MAP: dict[str, tuple[CheckType, str, str]] = {
    "tests":      ("tests",           "Tests",                 "pytest"),
    "build":      ("build",           "Build",                 "npm run build"),
    "lint":       ("lint",            "Lint",                  ""),
    "typecheck":  ("typecheck",       "Typecheck",             ""),
    "coverage":   ("coverage",        "Coverage",              ""),
    "semgrep":    ("security_sast",   "Semgrep SAST",          "semgrep scan"),
    "osv":        ("dependency_scan", "OSV dependency scan",   "osv-scanner"),
    "trivy":      ("container_scan",  "Trivy container scan",  "trivy"),
    "gitleaks":   ("secret_scan",     "Gitleaks secret scan",  "gitleaks detect"),
    "axe":        ("accessibility",   "axe accessibility",     ""),
    "playwright": ("e2e",             "Playwright e2e",        ""),
}


def _suggested_definitions(
    required_checks: list[str],
    project_id: str,
    code_repository_id: str | None,
) -> list[CheckDefinition]:
    """Pure helper: returns unsaved CheckDefinition instances for recognized keys."""
    now = datetime.now(timezone.utc)
    result: list[CheckDefinition] = []
    for key in required_checks:
        mapping = _CHECK_MAP.get(key)
        if mapping is None:
            continue
        check_type, name, command = mapping
        result.append(
            CheckDefinition(
                id=str(uuid.uuid4()),
                project_id=project_id,
                code_repository_id=code_repository_id,
                name=name,
                check_type=check_type,
                command=command,
                required=True,
                enabled=True,
                severity="blocking",
                description="",
                created_at=now,
                updated_at=now,
            )
        )
    return result


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
    assignment_fields = {"epic_id", "assignee_type", "assignee_id", "assignee_name"}
    changed_assignment = [f for f in assignment_fields if f in patch and getattr(dev_task, f) != patch[f]]
    if changed_assignment:
        _audit(
            "dev_task_assigned", "dev_task", dev_task.id,
            project_id=dev_task.project_id, actor_email=current_user,
            details={"changed_fields": changed_assignment},
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
    subtask_assignment_fields = {"assignee_type", "assignee_id", "assignee_name"}
    changed_subtask_assignment = [f for f in subtask_assignment_fields if f in patch and getattr(subtask, f) != patch[f]]
    if changed_subtask_assignment:
        _audit(
            "subtask_assigned", "subtask", subtask.id,
            project_id=subtask.project_id, actor_email=current_user,
            details={"changed_fields": changed_subtask_assignment},
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


# ---------------------------------------------------------------------------
# Epics
# ---------------------------------------------------------------------------

@app.post("/projects/{project_id}/epics", response_model=Epic, status_code=201)
def create_epic(
    project_id: str,
    body: EpicCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.requirement_id is not None:
        req = requirement_repo.get(body.requirement_id)
        if req is None:
            raise HTTPException(status_code=404, detail="Requirement not found")
        if req.project_id != project_id:
            raise HTTPException(status_code=404, detail="Requirement not found")
    now = datetime.now(timezone.utc)
    epic = Epic(
        id=str(uuid.uuid4()),
        project_id=project_id,
        requirement_id=body.requirement_id,
        title=body.title,
        description=body.description,
        status="proposed",
        priority=body.priority,
        sequence_order=body.sequence_order,
        acceptance_criteria=body.acceptance_criteria,
        business_goal=body.business_goal,
        assignee_type=body.assignee_type,
        assignee_id=body.assignee_id,
        assignee_name=body.assignee_name,
        created_at=now,
        updated_at=now,
    )
    epic_repo.save(epic)
    _audit(
        "epic_created", "epic", epic.id,
        project_id=project_id, actor_email=current_user,
    )
    return epic


@app.get("/projects/{project_id}/epics", response_model=list[Epic])
def list_project_epics(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return epic_repo.list_by_project(project_id)


@app.get("/requirements/{requirement_id}/epics", response_model=list[Epic])
def list_requirement_epics(requirement_id: str, _: str = Depends(require_auth)):
    if requirement_repo.get(requirement_id) is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return epic_repo.list_by_requirement(requirement_id)


@app.get("/epics/{epic_id}", response_model=Epic)
def get_epic(epic_id: str, _: str = Depends(require_auth)):
    epic = epic_repo.get(epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic


@app.patch("/epics/{epic_id}", response_model=Epic)
def update_epic(
    epic_id: str,
    body: EpicUpdate,
    current_user: str = Depends(require_auth),
):
    epic = epic_repo.get(epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return epic
    updated = epic.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    epic_repo.update(updated)
    _audit(
        "epic_updated", "epic", epic.id,
        project_id=epic.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated


# ---------------------------------------------------------------------------
# Check definitions (Task 25)
# ---------------------------------------------------------------------------

@app.post(
    "/projects/{project_id}/check-definitions",
    response_model=CheckDefinition,
    status_code=201,
)
def create_check_definition(
    project_id: str,
    body: CheckDefinitionCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    now = datetime.now(timezone.utc)
    definition = CheckDefinition(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        name=body.name,
        check_type=body.check_type,
        command=body.command,
        required=body.required,
        enabled=body.enabled,
        severity=body.severity,
        description=body.description,
        created_at=now,
        updated_at=now,
    )
    check_definition_repo.save(definition)
    _audit(
        "check_definition_created", "check_definition", definition.id,
        project_id=project_id, actor_email=current_user,
        details={"check_type": definition.check_type, "name": definition.name},
    )
    return definition


@app.get("/projects/{project_id}/check-definitions", response_model=list[CheckDefinition])
def list_project_check_definitions(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_definition_repo.list_by_project(project_id)


@app.get("/check-definitions/{check_definition_id}", response_model=CheckDefinition)
def get_check_definition(check_definition_id: str, _: str = Depends(require_auth)):
    definition = check_definition_repo.get(check_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    return definition


@app.patch("/check-definitions/{check_definition_id}", response_model=CheckDefinition)
def update_check_definition(
    check_definition_id: str,
    body: CheckDefinitionUpdate,
    current_user: str = Depends(require_auth),
):
    definition = check_definition_repo.get(check_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return definition
    updated = definition.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    check_definition_repo.update(updated)
    _audit(
        "check_definition_updated", "check_definition", definition.id,
        project_id=definition.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated


@app.post(
    "/projects/{project_id}/check-definitions/from-safety-profile",
    response_model=CheckDefinitionsFromSafetyProfileResponse,
    status_code=201,
)
def create_check_definitions_from_safety_profile(
    project_id: str,
    body: CheckDefinitionsFromSafetyProfileRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    code_repository_id: str | None = body.code_repository_id if body else None
    if code_repository_id is not None:
        if code_repo_repo.get(code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")

    # Resolve required_checks: use saved safety profile if available, else defaults.
    profile: RepoSafetyProfile | None = None
    if code_repository_id is not None:
        profile = repo_safety_profile_repo.get_by_repo(code_repository_id)
    required_checks = profile.required_checks if profile is not None else list(DEFAULT_REQUIRED_CHECKS)

    candidates = _suggested_definitions(required_checks, project_id, code_repository_id)

    # Dedupe: (code_repository_id, check_type, name) must be unique per project.
    existing_defs = check_definition_repo.list_by_project(project_id)
    existing_keys = {
        (d.code_repository_id, d.check_type, d.name)
        for d in existing_defs
    }

    newly_created: list[CheckDefinition] = []
    already_existing: list[CheckDefinition] = []

    for candidate in candidates:
        key = (candidate.code_repository_id, candidate.check_type, candidate.name)
        if key in existing_keys:
            # Find the matching existing definition to return it.
            match = next(
                (d for d in existing_defs if
                 d.code_repository_id == candidate.code_repository_id
                 and d.check_type == candidate.check_type
                 and d.name == candidate.name),
                None,
            )
            if match:
                already_existing.append(match)
        else:
            check_definition_repo.save(candidate)
            existing_keys.add(key)
            newly_created.append(candidate)
            _audit(
                "check_definition_created", "check_definition", candidate.id,
                project_id=project_id, actor_email=current_user,
                details={"check_type": candidate.check_type, "name": candidate.name, "source": "safety_profile"},
            )

    return CheckDefinitionsFromSafetyProfileResponse(
        created=newly_created,
        existing=already_existing,
    )


# ---------------------------------------------------------------------------
# Check runs (Task 25)
# ---------------------------------------------------------------------------

@app.post("/check-runs", response_model=CheckRun, status_code=201)
def record_check_run(
    body: CheckRunCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.check_definition_id is not None:
        if check_definition_repo.get(body.check_definition_id) is None:
            raise HTTPException(status_code=404, detail="CheckDefinition not found")
    now = datetime.now(timezone.utc)
    run = CheckRun(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        code_repository_id=body.code_repository_id,
        check_definition_id=body.check_definition_id,
        target_type=body.target_type,
        target_id=body.target_id,
        status=body.status,
        conclusion=body.conclusion,
        summary=body.summary,
        output=body.output,
        artifact_id=None,
        started_at=body.started_at or now,
        completed_at=body.completed_at,
        created_at=now,
        updated_at=now,
    )
    check_run_repo.save(run)
    _audit(
        "check_run_recorded", "check_run", run.id,
        project_id=body.project_id, actor_email=current_user,
        details={
            "target_type": run.target_type,
            "target_id": run.target_id,
            "conclusion": run.conclusion,
            "check_definition_id": run.check_definition_id,
        },
    )
    return run


@app.get("/projects/{project_id}/check-runs", response_model=list[CheckRun])
def list_project_check_runs(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_run_repo.list_by_project(project_id)


@app.get("/check-runs/{check_run_id}", response_model=CheckRun)
def get_check_run(check_run_id: str, _: str = Depends(require_auth)):
    run = check_run_repo.get(check_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="CheckRun not found")
    return run


@app.get("/dev-tasks/{dev_task_id}/check-runs", response_model=list[CheckRun])
def list_dev_task_check_runs(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return check_run_repo.list_by_target("dev_task", dev_task_id)


# ---------------------------------------------------------------------------
# Tool runner definitions (Task 26)
# ---------------------------------------------------------------------------

import re as _re

_SECRET_KEY_RE = _re.compile(r"(api[_-]?key|token|secret|password|credential)", _re.IGNORECASE)

_DEFAULT_RUNNER_TEMPLATES: list[dict] = [
    {
        "name": "OpenHands",
        "runner_type": "openhands",
        "mode": "dry_run",
        "enabled": False,
        "description": "Primary coding runner planned for Release 5. Tracking only — no execution.",
        "config": {"notes": "No execution yet"},
    },
    {
        "name": "Manual Runner",
        "runner_type": "manual",
        "mode": "manual",
        "enabled": True,
        "description": "Records manual implementation work as tool run results.",
        "config": {},
    },
]


def _validate_config_no_secrets(config_dict: dict) -> None:
    """Raise 400 if any config key looks like a secret field."""
    for key in config_dict:
        if _SECRET_KEY_RE.search(key):
            raise HTTPException(
                status_code=400,
                detail=f"config key '{key}' looks like a secret field. "
                       "Store secrets via a secret provider, not in config.",
            )


def _suggested_runner_definitions(
    project_id: str,
    code_repository_id: str | None,
) -> list[ToolRunnerDefinition]:
    """Returns unsaved ToolRunnerDefinition instances for the default runner set."""
    now = datetime.now(timezone.utc)
    result: list[ToolRunnerDefinition] = []
    for tpl in _DEFAULT_RUNNER_TEMPLATES:
        result.append(
            ToolRunnerDefinition(
                id=str(uuid.uuid4()),
                project_id=project_id,
                code_repository_id=code_repository_id,
                name=tpl["name"],
                runner_type=tpl["runner_type"],  # type: ignore[arg-type]
                enabled=tpl["enabled"],
                mode=tpl["mode"],  # type: ignore[arg-type]
                description=tpl["description"],
                config=dict(tpl["config"]),
                created_at=now,
                updated_at=now,
            )
        )
    return result


@app.post(
    "/projects/{project_id}/tool-runner-definitions",
    response_model=ToolRunnerDefinition,
    status_code=201,
)
def create_tool_runner_definition(
    project_id: str,
    body: ToolRunnerDefinitionCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    _validate_config_no_secrets(body.config)
    now = datetime.now(timezone.utc)
    definition = ToolRunnerDefinition(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        name=body.name,
        runner_type=body.runner_type,
        enabled=body.enabled,
        mode=body.mode,
        description=body.description,
        config=body.config,
        created_at=now,
        updated_at=now,
    )
    tool_runner_definition_repo.save(definition)
    _audit(
        "tool_runner_definition_created", "tool_runner_definition", definition.id,
        project_id=project_id, actor_email=current_user,
        details={"runner_type": definition.runner_type, "name": definition.name, "source": "manual"},
    )
    return definition


@app.get(
    "/projects/{project_id}/tool-runner-definitions",
    response_model=list[ToolRunnerDefinition],
)
def list_project_tool_runner_definitions(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tool_runner_definition_repo.list_by_project(project_id)


@app.get("/tool-runner-definitions/{tool_runner_definition_id}", response_model=ToolRunnerDefinition)
def get_tool_runner_definition(tool_runner_definition_id: str, _: str = Depends(require_auth)):
    definition = tool_runner_definition_repo.get(tool_runner_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    return definition


@app.patch("/tool-runner-definitions/{tool_runner_definition_id}", response_model=ToolRunnerDefinition)
def update_tool_runner_definition(
    tool_runner_definition_id: str,
    body: ToolRunnerDefinitionUpdate,
    current_user: str = Depends(require_auth),
):
    definition = tool_runner_definition_repo.get(tool_runner_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return definition
    if "config" in patch:
        _validate_config_no_secrets(patch["config"])
    updated = definition.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    tool_runner_definition_repo.update(updated)
    _audit(
        "tool_runner_definition_updated", "tool_runner_definition", definition.id,
        project_id=definition.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated


@app.post(
    "/projects/{project_id}/tool-runner-definitions/defaults",
    response_model=ToolRunnerDefinitionsDefaultsResponse,
    status_code=201,
)
def create_default_tool_runner_definitions(
    project_id: str,
    body: ToolRunnerDefinitionsDefaultsRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    code_repository_id: str | None = body.code_repository_id if body else None
    if code_repository_id is not None:
        if code_repo_repo.get(code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")

    candidates = _suggested_runner_definitions(project_id, code_repository_id)

    # Dedupe: (code_repository_id, runner_type, name) must be unique per project.
    existing_defs = tool_runner_definition_repo.list_by_project(project_id)
    existing_keys = {
        (d.code_repository_id, d.runner_type, d.name)
        for d in existing_defs
    }

    newly_created: list[ToolRunnerDefinition] = []
    already_existing: list[ToolRunnerDefinition] = []

    for candidate in candidates:
        key = (candidate.code_repository_id, candidate.runner_type, candidate.name)
        if key in existing_keys:
            match = next(
                (d for d in existing_defs if
                 d.code_repository_id == candidate.code_repository_id
                 and d.runner_type == candidate.runner_type
                 and d.name == candidate.name),
                None,
            )
            if match:
                already_existing.append(match)
        else:
            tool_runner_definition_repo.save(candidate)
            existing_keys.add(key)
            newly_created.append(candidate)
            _audit(
                "tool_runner_definition_created", "tool_runner_definition", candidate.id,
                project_id=project_id, actor_email=current_user,
                details={"runner_type": candidate.runner_type, "name": candidate.name, "source": "defaults"},
            )

    return ToolRunnerDefinitionsDefaultsResponse(
        created=newly_created,
        existing=already_existing,
    )


# ---------------------------------------------------------------------------
# Tool runs (Task 26)
# ---------------------------------------------------------------------------

@app.post("/tool-runs", response_model=ToolRun, status_code=201)
def record_tool_run(
    body: ToolRunCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.tool_runner_definition_id is not None:
        if tool_runner_definition_repo.get(body.tool_runner_definition_id) is None:
            raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    now = datetime.now(timezone.utc)
    run = ToolRun(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        code_repository_id=body.code_repository_id,
        tool_runner_definition_id=body.tool_runner_definition_id,
        target_type=body.target_type,
        target_id=body.target_id,
        runner_type=body.runner_type,
        mode=body.mode,
        status=body.status,
        conclusion=body.conclusion,
        summary=body.summary,
        output=body.output,
        artifact_id=None,
        started_at=body.started_at or now,
        completed_at=body.completed_at,
        created_at=now,
        updated_at=now,
    )
    tool_run_repo.save(run)
    _audit(
        "tool_run_recorded", "tool_run", run.id,
        project_id=body.project_id, actor_email=current_user,
        details={
            "runner_type": run.runner_type,
            "target_type": run.target_type,
            "target_id": run.target_id,
            "conclusion": run.conclusion,
            "tool_runner_definition_id": run.tool_runner_definition_id,
        },
    )
    return run


@app.get("/projects/{project_id}/tool-runs", response_model=list[ToolRun])
def list_project_tool_runs(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tool_run_repo.list_by_project(project_id)


@app.get("/tool-runs/{tool_run_id}", response_model=ToolRun)
def get_tool_run(tool_run_id: str, _: str = Depends(require_auth)):
    run = tool_run_repo.get(tool_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ToolRun not found")
    return run


@app.get("/dev-tasks/{dev_task_id}/tool-runs", response_model=list[ToolRun])
def list_dev_task_tool_runs(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return tool_run_repo.list_by_target("dev_task", dev_task_id)


@app.get("/subtasks/{subtask_id}/tool-runs", response_model=list[ToolRun])
def list_subtask_tool_runs(subtask_id: str, _: str = Depends(require_auth)):
    if subtask_repo.get(subtask_id) is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    return tool_run_repo.list_by_target("subtask", subtask_id)


# ---------------------------------------------------------------------------
# OpenHandsRunner (Task 27) — instruction-package dry-run only
# ---------------------------------------------------------------------------

_OPENHANDS_RUNNER = OpenHandsRunner()


def _resolve_code_repository(
    project_id: str,
    requested_repo_id: str | None,
    definition: ToolRunnerDefinition | None,
):
    """Resolve a CodeRepository for the OpenHands package, or None.

    Precedence: explicit request > definition.code_repository_id > sole project repo.
    Raises 404 if a requested id is missing.
    """
    repo_id = requested_repo_id or (definition.code_repository_id if definition else None)
    if repo_id is not None:
        cr = code_repo_repo.get(repo_id)
        if cr is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
        if cr.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="CodeRepository does not belong to dev task's project",
            )
        return cr
    project_repos = code_repo_repo.list_by_project(project_id)
    if len(project_repos) == 1:
        return project_repos[0]
    return None


@app.post(
    "/dev-tasks/{dev_task_id}/openhands/prepare",
    response_model=OpenHandsPrepareResponse,
    status_code=201,
)
def prepare_openhands_package(
    dev_task_id: str,
    body: OpenHandsPreparePackageRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    project = project_repo.get(dev_task.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    body = body or OpenHandsPreparePackageRequest()

    definition: ToolRunnerDefinition | None = None
    if body.tool_runner_definition_id is not None:
        definition = tool_runner_definition_repo.get(body.tool_runner_definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
        if definition.runner_type != "openhands":
            raise HTTPException(
                status_code=400,
                detail="ToolRunnerDefinition is not an OpenHands runner",
            )
        if not definition.enabled:
            raise HTTPException(
                status_code=400,
                detail="OpenHands runner definition is disabled",
            )

    if _config.OPENHANDS_MODE not in ("dry_run", "manual") and not _config.OPENHANDS_EXECUTION_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="OpenHands execution is disabled (OPENHANDS_EXECUTION_ENABLED=false)",
        )

    code_repository = _resolve_code_repository(
        dev_task.project_id, body.code_repository_id, definition
    )
    safety_profile = (
        repo_safety_profile_repo.get_by_repo(code_repository.id)
        if code_repository is not None
        else None
    )
    project_context = project_context_repo.get(project.id)

    requirement_summary: str | None = None
    if dev_task.requirement_id:
        req = requirement_repo.get(dev_task.requirement_id)
        if req is not None:
            requirement_summary = req.problem_statement or req.title

    epic_title: str | None = None
    if dev_task.epic_id:
        epic = epic_repo.get(dev_task.epic_id)
        if epic is not None:
            epic_title = epic.title

    package_dict = _OPENHANDS_RUNNER.prepare_run(
        project=project,
        dev_task=dev_task,
        code_repository=code_repository,
        safety_profile=safety_profile,
        project_context=project_context,
        definition=definition,
        requirement_summary=requirement_summary,
        epic_title=epic_title,
    )

    now = datetime.now(timezone.utc)
    run = ToolRun(
        id=str(uuid.uuid4()),
        project_id=project.id,
        code_repository_id=code_repository.id if code_repository is not None else None,
        tool_runner_definition_id=definition.id if definition is not None else None,
        target_type="dev_task",
        target_id=dev_task.id,
        runner_type="openhands",
        mode="dry_run",
        status="completed",
        conclusion="requires_human_action",
        summary="OpenHands instruction package prepared",
        output=json.dumps(package_dict, sort_keys=True),
        artifact_id=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    tool_run_repo.save(run)
    _audit(
        "openhands_package_prepared", "tool_run", run.id,
        project_id=project.id, actor_email=current_user,
        details={
            "dev_task_id": dev_task.id,
            "tool_run_id": run.id,
            "code_repository_id": run.code_repository_id,
            "safety_profile_present": safety_profile is not None,
        },
    )
    return OpenHandsPrepareResponse(
        tool_run=run,
        instruction_package=OpenHandsInstructionPackage(**package_dict),
    )


@app.post(
    "/tool-runs/{tool_run_id}/openhands/record-result",
    response_model=ToolRun,
)
def record_openhands_result(
    tool_run_id: str,
    body: OpenHandsRecordResultRequest,
    current_user: str = Depends(require_auth),
):
    run = tool_run_repo.get(tool_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ToolRun not found")
    if run.runner_type != "openhands":
        raise HTTPException(
            status_code=400,
            detail="ToolRun is not an OpenHands run",
        )
    updated = _OPENHANDS_RUNNER.record_result(
        tool_run=run,
        summary=body.summary,
        output=body.output,
        conclusion=body.conclusion,
    )
    tool_run_repo.save(updated)
    _audit(
        "openhands_result_recorded", "tool_run", updated.id,
        project_id=updated.project_id, actor_email=current_user,
        details={"tool_run_id": updated.id, "conclusion": updated.conclusion},
    )
    return updated


# ---------------------------------------------------------------------------
# PR draft workflow (Task 28) — manual tracking only, no GitHub API
# ---------------------------------------------------------------------------

_PR_DRAFT_ALLOWED_PROVIDERS = ("manual", "local")


@app.post(
    "/projects/{project_id}/pr-drafts",
    response_model=PullRequestDraft,
    status_code=201,
)
def create_pr_draft(
    project_id: str,
    body: PullRequestDraftCreate,
    current_user: str = Depends(require_auth),
):
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    repo_obj = code_repo_repo.get(body.code_repository_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    if repo_obj.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="CodeRepository does not belong to project",
        )

    if body.dev_task_id is None and body.subtask_id is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of dev_task_id or subtask_id is required",
        )

    if body.provider not in _PR_DRAFT_ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"provider={body.provider!r} is not supported in this build. "
                f"Allowed: {list(_PR_DRAFT_ALLOWED_PROVIDERS)}."
            ),
        )

    dev_task = None
    if body.dev_task_id is not None:
        dev_task = dev_task_repo.get(body.dev_task_id)
        if dev_task is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
        if dev_task.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="DevTask does not belong to project",
            )

    subtask = None
    if body.subtask_id is not None:
        subtask = subtask_repo.get(body.subtask_id)
        if subtask is None:
            raise HTTPException(status_code=404, detail="Subtask not found")
        if subtask.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="Subtask does not belong to project",
            )

    tool_run = None
    if body.tool_run_id is not None:
        tool_run = tool_run_repo.get(body.tool_run_id)
        if tool_run is None:
            raise HTTPException(status_code=404, detail="ToolRun not found")

    safety_profile = repo_safety_profile_repo.get_by_repo(repo_obj.id)

    requirement = None
    epic = None
    if dev_task is not None:
        if dev_task.requirement_id:
            requirement = requirement_repo.get(dev_task.requirement_id)
        if dev_task.epic_id:
            epic = epic_repo.get(dev_task.epic_id)

    check_runs: list = []
    if dev_task is not None:
        check_runs = check_run_repo.list_by_target("dev_task", dev_task.id)
    elif subtask is not None:
        check_runs = check_run_repo.list_by_target("subtask", subtask.id)

    generated_title, generated_body = build_pr_draft_content(
        project=project,
        code_repository=repo_obj,
        safety_profile=safety_profile,
        dev_task=dev_task,
        subtask=subtask,
        requirement=requirement,
        epic=epic,
        tool_run=tool_run,
        check_runs=check_runs,
    )

    title = body.title.strip() if body.title else generated_title
    if not title:
        title = generated_title
    pr_body = body.body if body.body is not None else generated_body
    source_branch = body.source_branch or derive_source_branch(dev_task, subtask)

    now = datetime.now(timezone.utc)
    draft = PullRequestDraft(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=repo_obj.id,
        dev_task_id=body.dev_task_id,
        subtask_id=body.subtask_id,
        tool_run_id=body.tool_run_id,
        title=title,
        body=pr_body,
        source_branch=source_branch,
        target_branch=body.target_branch or "main",
        status="draft_prepared",
        provider=body.provider,
        external_pr_url=None,
        external_pr_number=None,
        created_by=current_user or "system",
        error_message=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
    )
    pr_draft_repo.save(draft)
    _audit(
        "pr_draft_prepared", "pr_draft", draft.id,
        project_id=project_id, actor_email=current_user,
        details={
            "pr_draft_id": draft.id,
            "dev_task_id": draft.dev_task_id,
            "subtask_id": draft.subtask_id,
            "tool_run_id": draft.tool_run_id,
            "code_repository_id": draft.code_repository_id,
            "provider": draft.provider,
        },
    )
    return draft


@app.get("/projects/{project_id}/pr-drafts", response_model=list[PullRequestDraft])
def list_project_pr_drafts(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pr_draft_repo.list_by_project(project_id)


@app.get("/pr-drafts/{pr_draft_id}", response_model=PullRequestDraft)
def get_pr_draft(pr_draft_id: str, _: str = Depends(require_auth)):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return draft


@app.patch("/pr-drafts/{pr_draft_id}", response_model=PullRequestDraft)
def patch_pr_draft(
    pr_draft_id: str,
    body: PullRequestDraftUpdate,
    current_user: str = Depends(require_auth),
):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return draft
    if "status" in patch and patch["status"] is not None:
        target = patch["status"]
        if target == "approved_for_creation":
            raise HTTPException(
                status_code=400,
                detail="Use POST /pr-drafts/{id}/approve to set approved_for_creation",
            )
        if not is_allowed_status_transition(draft.status, target):
            raise HTTPException(
                status_code=400,
                detail=f"Disallowed status transition: {draft.status} -> {target}",
            )
    updated = draft.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    pr_draft_repo.update(updated)
    _audit(
        "pr_draft_updated", "pr_draft", draft.id,
        project_id=draft.project_id, actor_email=current_user,
        details={"pr_draft_id": draft.id, "changed_fields": list(patch.keys())},
    )
    return updated


@app.post("/pr-drafts/{pr_draft_id}/approve", response_model=PullRequestDraft)
def approve_pr_draft(
    pr_draft_id: str,
    current_user: str = Depends(require_auth),
):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    if draft.status not in ("draft_prepared", "awaiting_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"PullRequestDraft in status {draft.status!r} cannot be approved",
        )
    now = datetime.now(timezone.utc)
    updated = draft.model_copy(
        update={
            "status": "approved_for_creation",
            "approved_at": now,
            "updated_at": now,
        }
    )
    pr_draft_repo.update(updated)
    _audit(
        "pr_draft_approved", "pr_draft", draft.id,
        project_id=draft.project_id, actor_email=current_user,
        details={"pr_draft_id": draft.id},
    )
    return updated


# ---------------------------------------------------------------------------
# PR review integration foundation (Task 29)
# ---------------------------------------------------------------------------

_kody_review_adapter = KodyReviewAdapter()


def _gather_review_context(draft: PullRequestDraft):
    project = project_repo.get(draft.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    code_repository = code_repo_repo.get(draft.code_repository_id)
    if code_repository is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")

    dev_task = dev_task_repo.get(draft.dev_task_id) if draft.dev_task_id else None
    subtask = subtask_repo.get(draft.subtask_id) if draft.subtask_id else None
    tool_run = tool_run_repo.get(draft.tool_run_id) if draft.tool_run_id else None
    safety_profile = repo_safety_profile_repo.get_by_repo(code_repository.id)

    requirement = None
    epic = None
    if dev_task is not None:
        if dev_task.requirement_id:
            requirement = requirement_repo.get(dev_task.requirement_id)
        if dev_task.epic_id:
            epic = epic_repo.get(dev_task.epic_id)

    check_runs: list = []
    if dev_task is not None:
        check_runs = check_run_repo.list_by_target("dev_task", dev_task.id)
    elif subtask is not None:
        check_runs = check_run_repo.list_by_target("subtask", subtask.id)

    approvals: list = []
    if dev_task is not None or subtask is not None:
        target_type = "dev_task" if dev_task is not None else "subtask"
        target_id = dev_task.id if dev_task is not None else subtask.id
        approvals = [
            a for a in approval_repo.list_by_project(draft.project_id)
            if a.target_type == target_type and a.target_id == target_id
        ]

    return (
        project,
        code_repository,
        safety_profile,
        dev_task,
        subtask,
        requirement,
        epic,
        tool_run,
        check_runs,
        approvals,
    )


@app.post(
    "/pr-drafts/{pr_draft_id}/reviews",
    response_model=PullRequestReview,
    status_code=201,
)
def create_pr_review(
    pr_draft_id: str,
    body: PullRequestReviewCreate,
    current_user: str = Depends(require_auth),
):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")

    (
        project,
        code_repository,
        safety_profile,
        dev_task,
        subtask,
        requirement,
        epic,
        tool_run,
        check_runs,
        approvals,
    ) = _gather_review_context(draft)

    now = datetime.now(timezone.utc)
    is_manual_completed = body.mode == "manual" and body.conclusion is not None

    if is_manual_completed:
        status = "completed"
        conclusion = body.conclusion
        completed_at = now
        started_at = now
        raw_output = body.raw_output
        summary = body.summary or ""
    else:
        package = build_kody_review_package(
            pr_draft=draft,
            project=project,
            code_repository=code_repository,
            safety_profile=safety_profile,
            dev_task=dev_task,
            subtask=subtask,
            requirement=requirement,
            epic=epic,
            tool_run=tool_run,
            check_runs=check_runs,
            approvals=approvals,
        )
        status = "pending"
        conclusion = None
        completed_at = None
        started_at = None
        raw_output = body.raw_output if body.raw_output is not None else json.dumps(package)
        summary = body.summary or ""

    review = PullRequestReview(
        id=str(uuid.uuid4()),
        project_id=draft.project_id,
        code_repository_id=draft.code_repository_id,
        pr_draft_id=draft.id,
        provider=body.provider,
        status=status,
        conclusion=conclusion,
        summary=summary,
        findings=list(body.findings or []),
        recommendations=body.recommendations,
        raw_output=raw_output,
        artifact_id=None,
        external_review_url=body.external_review_url,
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
        error_message=None,
    )
    pr_review_repo.save(review)

    action: AuditAction = "pr_review_recorded" if is_manual_completed else "pr_review_requested"
    _audit(
        action, "pr_review", review.id,
        project_id=draft.project_id, actor_email=current_user,
        details={
            "pr_draft_id": draft.id,
            "review_id": review.id,
            "provider": review.provider,
            "conclusion": review.conclusion,
        },
    )
    return review


@app.get(
    "/pr-drafts/{pr_draft_id}/reviews",
    response_model=list[PullRequestReview],
)
def list_pr_draft_reviews(pr_draft_id: str, _: str = Depends(require_auth)):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return pr_review_repo.list_by_pr_draft(pr_draft_id)


@app.get("/pr-reviews/{review_id}", response_model=PullRequestReview)
def get_pr_review(review_id: str, _: str = Depends(require_auth)):
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    return review


@app.patch("/pr-reviews/{review_id}", response_model=PullRequestReview)
def patch_pr_review(
    review_id: str,
    body: PullRequestReviewUpdate,
    current_user: str = Depends(require_auth),
):
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return review

    target_status = patch.get("status")
    if target_status is not None:
        if not is_allowed_review_status_transition(review.status, target_status):
            raise HTTPException(
                status_code=400,
                detail=f"Disallowed status transition: {review.status} -> {target_status}",
            )
        if target_status == "completed":
            target_conclusion = patch.get("conclusion", review.conclusion)
            if target_conclusion is None:
                raise HTTPException(
                    status_code=400,
                    detail="conclusion is required when transitioning to status=completed",
                )

    if "findings" in patch and body.findings is not None:
        patch["findings"] = list(body.findings)

    now = datetime.now(timezone.utc)
    update_fields: dict = {**patch, "updated_at": now}
    if target_status == "completed" and review.completed_at is None:
        update_fields["completed_at"] = now
    if target_status == "running" and review.started_at is None:
        update_fields["started_at"] = now

    updated = review.model_copy(update=update_fields)
    pr_review_repo.update(updated)

    material_fields = {"summary", "findings", "conclusion"}
    if material_fields.intersection(patch.keys()):
        _audit(
            "pr_review_recorded", "pr_review", review.id,
            project_id=review.project_id, actor_email=current_user,
            details={
                "pr_draft_id": review.pr_draft_id,
                "review_id": review.id,
                "changed_fields": list(patch.keys()),
            },
        )
    return updated


@app.post(
    "/pr-reviews/{review_id}/complete",
    response_model=PullRequestReview,
)
def complete_pr_review(
    review_id: str,
    body: PullRequestReviewComplete,
    current_user: str = Depends(require_auth),
):
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    if review.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="PullRequestReview is already completed",
        )
    if not is_allowed_review_status_transition(review.status, "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"PullRequestReview in status {review.status!r} cannot be completed",
        )

    now = datetime.now(timezone.utc)
    updated = _kody_review_adapter.record_review_result(
        review=review,
        conclusion=body.conclusion,
        summary=body.summary or "",
        findings=list(body.findings or []),
        recommendations=body.recommendations,
        raw_output=body.raw_output,
    )
    if updated.started_at is None:
        updated = updated.model_copy(update={"started_at": now})
    pr_review_repo.update(updated)
    _audit(
        "pr_review_completed", "pr_review", review.id,
        project_id=review.project_id, actor_email=current_user,
        details={
            "pr_draft_id": review.pr_draft_id,
            "review_id": review.id,
            "conclusion": updated.conclusion,
        },
    )
    return updated


# ---------------------------------------------------------------------------
# CI failure ingestion and analysis (Task 30)
# ---------------------------------------------------------------------------

@app.post(
    "/projects/{project_id}/ci-events",
    response_model=CIEvent,
    status_code=201,
)
def record_ci_event(
    project_id: str,
    body: CIEventCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.code_repository_id is not None:
        repo_obj = code_repo_repo.get(body.code_repository_id)
        if repo_obj is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.pr_draft_id is not None:
        if pr_draft_repo.get(body.pr_draft_id) is None:
            raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    if body.dev_task_id is not None:
        if dev_task_repo.get(body.dev_task_id) is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
    if body.subtask_id is not None:
        if subtask_repo.get(body.subtask_id) is None:
            raise HTTPException(status_code=404, detail="Subtask not found")
    if body.check_run_id is not None:
        if check_run_repo.get(body.check_run_id) is None:
            raise HTTPException(status_code=404, detail="CheckRun not found")

    now = datetime.now(timezone.utc)
    event = CIEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        pr_draft_id=body.pr_draft_id,
        dev_task_id=body.dev_task_id,
        subtask_id=body.subtask_id,
        check_run_id=body.check_run_id,
        provider=body.provider,
        external_run_id=body.external_run_id,
        workflow_name=body.workflow_name,
        job_name=body.job_name,
        branch=body.branch,
        commit_sha=body.commit_sha,
        pr_number=body.pr_number,
        pr_url=body.pr_url,
        status=body.status,
        conclusion=body.conclusion,
        failure_summary=body.failure_summary,
        logs_excerpt=body.logs_excerpt,
        raw_payload=body.raw_payload,
        artifact_id=None,
        created_at=now,
        updated_at=now,
    )
    ci_event_repo.save(event)
    _audit(
        "ci_event_recorded", "ci_event", event.id,
        project_id=project_id, actor_email=current_user,
        details={
            "provider": event.provider,
            "workflow_name": event.workflow_name,
            "job_name": event.job_name,
            "conclusion": event.conclusion,
            "pr_draft_id": event.pr_draft_id,
            "dev_task_id": event.dev_task_id,
            "check_run_id": event.check_run_id,
        },
    )
    return event


@app.get("/projects/{project_id}/ci-events", response_model=list[CIEvent])
def list_project_ci_events(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ci_event_repo.list_by_project(project_id)


@app.get("/ci-events/{ci_event_id}", response_model=CIEvent)
def get_ci_event(ci_event_id: str, _: str = Depends(require_auth)):
    event = ci_event_repo.get(ci_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")
    return event


@app.get("/pr-drafts/{pr_draft_id}/ci-events", response_model=list[CIEvent])
def list_pr_draft_ci_events(pr_draft_id: str, _: str = Depends(require_auth)):
    if pr_draft_repo.get(pr_draft_id) is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return ci_event_repo.list_by_pr_draft(pr_draft_id)


@app.get("/dev-tasks/{dev_task_id}/ci-events", response_model=list[CIEvent])
def list_dev_task_ci_events(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return ci_event_repo.list_by_dev_task(dev_task_id)


@app.post(
    "/ci-events/{ci_event_id}/analysis",
    response_model=CIAnalysis,
    status_code=201,
)
def create_ci_analysis(
    ci_event_id: str,
    body: CIAnalysisCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    event = ci_event_repo.get(ci_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")

    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pr_draft = pr_draft_repo.get(event.pr_draft_id) if event.pr_draft_id else None
    dev_task = dev_task_repo.get(event.dev_task_id) if event.dev_task_id else None
    subtask = subtask_repo.get(event.subtask_id) if event.subtask_id else None
    check_run = check_run_repo.get(event.check_run_id) if event.check_run_id else None
    project_context = project_context_repo.get(event.project_id)

    analysis_id = str(uuid.uuid4())
    _audit(
        "ci_analysis_requested", "ci_analysis", analysis_id,
        project_id=event.project_id, actor_email=current_user,
        details={
            "ci_event_id": event.id,
            "provider": provider.provider_name,
        },
    )

    now = datetime.now(timezone.utc)
    try:
        parsed = run_ci_failure_analysis(
            ci_event=event,
            provider=provider,
            project_context=project_context,
            pr_draft=pr_draft,
            dev_task=dev_task,
            subtask=subtask,
            check_run=check_run,
        )
    except Exception as exc:
        failed = CIAnalysis(
            id=analysis_id,
            project_id=event.project_id,
            ci_event_id=event.id,
            provider=provider.provider_name,
            model=provider.model_name,
            status="failed",
            conclusion="unknown",
            summary="",
            likely_root_causes=[],
            suggested_fixes=[],
            affected_areas=[],
            recommended_next_action=None,
            raw_output=None,
            artifact_id=None,
            error_message=str(exc),
            created_at=now,
            updated_at=now,
        )
        ci_analysis_repo.save(failed)
        _audit(
            "ci_analysis_failed", "ci_analysis", failed.id,
            project_id=event.project_id, actor_email=current_user,
            details={
                "ci_event_id": event.id,
                "provider": provider.provider_name,
                "error": str(exc),
            },
        )
        return failed

    analysis = CIAnalysis(
        id=analysis_id,
        project_id=event.project_id,
        ci_event_id=event.id,
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        conclusion=parsed.get("conclusion") or "unknown",
        summary=parsed.get("summary", ""),
        likely_root_causes=list(parsed.get("likely_root_causes") or []),
        suggested_fixes=list(parsed.get("suggested_fixes") or []),
        affected_areas=list(parsed.get("affected_areas") or []),
        recommended_next_action=parsed.get("recommended_next_action"),
        raw_output=parsed.get("raw_output"),
        artifact_id=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    ci_analysis_repo.save(analysis)
    _audit(
        "ci_analysis_completed", "ci_analysis", analysis.id,
        project_id=event.project_id, actor_email=current_user,
        details={
            "ci_event_id": event.id,
            "provider": analysis.provider,
            "conclusion": analysis.conclusion,
        },
    )
    return analysis


@app.get("/ci-events/{ci_event_id}/analyses", response_model=list[CIAnalysis])
def list_ci_event_analyses(ci_event_id: str, _: str = Depends(require_auth)):
    if ci_event_repo.get(ci_event_id) is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")
    return ci_analysis_repo.list_by_ci_event(ci_event_id)


@app.get("/ci-analyses/{analysis_id}", response_model=CIAnalysis)
def get_ci_analysis(analysis_id: str, _: str = Depends(require_auth)):
    analysis = ci_analysis_repo.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="CIAnalysis not found")
    return analysis
