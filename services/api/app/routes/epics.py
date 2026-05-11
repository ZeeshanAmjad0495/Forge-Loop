import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import Epic, EpicCreate, EpicUpdate
from ..repositories_state import audit_writer, epic_repo, project_repo, requirement_repo

router = APIRouter()


@router.post("/projects/{project_id}/epics", response_model=Epic, status_code=201)
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
    audit_writer.write(
        "epic_created", "epic", epic.id,
        project_id=project_id, actor_email=current_user,
    )
    return epic


@router.get("/projects/{project_id}/epics", response_model=list[Epic])
def list_project_epics(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return epic_repo.list_by_project(project_id)


@router.get("/requirements/{requirement_id}/epics", response_model=list[Epic])
def list_requirement_epics(requirement_id: str, _: str = Depends(require_auth)):
    if requirement_repo.get(requirement_id) is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return epic_repo.list_by_requirement(requirement_id)


@router.get("/epics/{epic_id}", response_model=Epic)
def get_epic(epic_id: str, _: str = Depends(require_auth)):
    epic = epic_repo.get(epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic


@router.patch("/epics/{epic_id}", response_model=Epic)
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
    audit_writer.write(
        "epic_updated", "epic", epic.id,
        project_id=epic.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated
