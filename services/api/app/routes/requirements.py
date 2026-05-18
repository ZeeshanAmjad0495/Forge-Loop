import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    Requirement,
    RequirementAnalysis,
    RequirementAnalysisRunCreate,
    RequirementAnalysisRunResponse,
    RequirementCreate,
    RequirementGenerationResponse,
    RequirementGenerationRunCreate,
    RequirementUpdate,
)
from ..repositories_state import (
    agent_run_repo,
    analysis_repo,
    artifact_repo,
    audit_writer,
    code_repo_repo,
    project_context_repo,
    project_repo,
    repo,
    repo_safety_profile_repo,
    requirement_repo,
)
from ..requirement_analysis_agent import (
    run_requirement_analysis_agent,
    run_requirement_analysis_for_requirement,
)
from ..requirement_generation_agent import run_requirement_generation_agent
from .common import resolve_routed_provider_or_400

router = APIRouter()


@router.post(
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
    provider, _route_decision = resolve_routed_provider_or_400(
        "requirement_analysis",
        body.provider if body else None,
        project_id=ticket.project_id,
        source_type="ticket",
        source_id=ticket.id,
        expensive_approved=(body.expensive_approved if body else False),
    )
    context = None
    if ticket.project_id:
        context = project_context_repo.get(ticket.project_id)
    run, analysis, artifact = run_requirement_analysis_agent(
        ticket, provider, agent_run_repo, artifact_repo, analysis_repo, context
    )
    return RequirementAnalysisRunResponse(agent_run=run, requirement_analysis=analysis, artifact=artifact)


@router.get("/tickets/{ticket_id}/requirement-analyses", response_model=list[RequirementAnalysis])
def list_requirement_analyses(ticket_id: str, _: str = Depends(require_auth)):
    if repo.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return analysis_repo.list_by_ticket(ticket_id)


@router.post("/projects/{project_id}/requirements", response_model=Requirement, status_code=201)
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
    audit_writer.write(
        "requirement_created", "requirement", requirement.id,
        project_id=project_id, actor_email=current_user,
    )
    return requirement


@router.get("/projects/{project_id}/requirements", response_model=list[Requirement])
def list_project_requirements(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return requirement_repo.list_by_project(project_id)


@router.get("/requirements/{requirement_id}", response_model=Requirement)
def get_requirement(requirement_id: str, _: str = Depends(require_auth)):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@router.put("/requirements/{requirement_id}", response_model=Requirement)
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


@router.post(
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
    provider, _route_decision = resolve_routed_provider_or_400(
        "requirement_analysis",
        body.provider if body else None,
        project_id=project_id,
        source_type="project",
        source_id=project_id,
        expensive_approved=(body.expensive_approved if body else False),
    )
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
    audit_writer.write(
        "requirement_generation_created", "agent_run", run.id,
        project_id=project_id, actor_email=current_user,
        details={
            "requirement_count": len(requirements),
            "provider": provider.provider_name,
        },
    )
    for requirement in requirements:
        audit_writer.write(
            "requirement_created", "requirement", requirement.id,
            project_id=project_id, actor_email=current_user,
            details={"source": "agent_generated"},
        )
    return RequirementGenerationResponse(
        agent_run=run, artifact=artifact, requirements=requirements,
    )


@router.post(
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
    provider, _route_decision = resolve_routed_provider_or_400(
        "requirement_analysis",
        body.provider if body else None,
        project_id=requirement.project_id,
        source_type="requirement",
        source_id=requirement.id,
        expensive_approved=(body.expensive_approved if body else False),
    )
    context = project_context_repo.get(requirement.project_id)
    run, analysis, artifact = run_requirement_analysis_for_requirement(
        requirement, provider, agent_run_repo, artifact_repo, analysis_repo, context
    )
    updated = requirement.model_copy(
        update={"status": "analyzed", "updated_at": datetime.now(timezone.utc)}
    )
    requirement_repo.update(updated)
    audit_writer.write(
        "requirement_analyzed", "requirement_analysis", analysis.id,
        project_id=requirement.project_id, actor_email=current_user,
        details={"requirement_id": requirement_id},
    )
    return RequirementAnalysisRunResponse(
        agent_run=run, requirement_analysis=analysis, artifact=artifact
    )
