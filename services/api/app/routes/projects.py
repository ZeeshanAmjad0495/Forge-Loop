import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    Project,
    ProjectContext,
    ProjectContextUpdate,
    ProjectCreate,
)
from ..repositories_state import project_context_repo, project_repo

router = APIRouter()


@router.post("/projects", response_model=Project, status_code=201)
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


@router.get("/projects", response_model=list[Project])
def list_projects(_: str = Depends(require_auth)):
    return project_repo.list_all()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str, _: str = Depends(require_auth)):
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/context", response_model=ProjectContext)
def get_project_context(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ctx = project_context_repo.get(project_id)
    if ctx is None:
        return ProjectContext(project_id=project_id)
    return ctx


@router.put("/projects/{project_id}/context", response_model=ProjectContext)
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
