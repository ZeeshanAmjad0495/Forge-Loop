from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    Workspace,
    WorkspaceCreate,
    WorkspaceInspection,
    WorkspaceUpdate,
)
from ..repositories_state import (
    audit_writer,
    code_repo_repo,
    project_repo,
    repo_safety_profile_repo,
    workspace_repo,
)
from ..services.workspaces import (
    CodeRepositoryNotFound,
    ProjectNotFound,
    WorkspaceNotFound,
    WorkspacePathError,
    WorkspaceService,
    WorkspaceValidationError,
)

router = APIRouter()


def _service() -> WorkspaceService:
    return WorkspaceService(
        workspace_repo=workspace_repo,
        project_repo=project_repo,
        code_repo_repo=code_repo_repo,
        repo_safety_profile_repo=repo_safety_profile_repo,
    )


@router.post(
    "/projects/{project_id}/workspaces",
    response_model=Workspace,
    status_code=201,
)
def create_workspace(
    project_id: str,
    body: WorkspaceCreate,
    current_user: str = Depends(require_auth),
):
    svc = _service()
    try:
        workspace = svc.create(project_id, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Project not found")
    except CodeRepositoryNotFound:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except WorkspaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if workspace.workspace_type == "local_created":
        action = "workspace_created"
    else:
        action = "workspace_registered"
    audit_writer.write(
        action,
        "workspace",
        workspace.id,
        project_id=project_id,
        actor_email=current_user,
        details={
            "workspace_type": workspace.workspace_type,
            "status": workspace.status,
            "code_repository_id": workspace.code_repository_id,
        },
    )
    if workspace.status in ("missing", "invalid"):
        audit_writer.write(
            "workspace_invalid",
            "workspace",
            workspace.id,
            project_id=project_id,
            actor_email=current_user,
            details={"status": workspace.status, "error_message": workspace.error_message},
        )
    return workspace


@router.get(
    "/projects/{project_id}/workspaces",
    response_model=list[Workspace],
)
def list_project_workspaces(project_id: str, _: str = Depends(require_auth)):
    svc = _service()
    try:
        return svc.list_by_project(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/workspaces/{workspace_id}", response_model=Workspace)
def get_workspace(workspace_id: str, _: str = Depends(require_auth)):
    svc = _service()
    try:
        return svc.get(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.patch("/workspaces/{workspace_id}", response_model=Workspace)
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    current_user: str = Depends(require_auth),
):
    svc = _service()
    try:
        updated = svc.update(workspace_id, body)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except CodeRepositoryNotFound:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    changed_fields = [k for k in body.model_dump(exclude_unset=True).keys()]
    audit_writer.write(
        "workspace_registered",
        "workspace",
        updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"changed_fields": changed_fields, "status": updated.status},
    )
    return updated


@router.post(
    "/workspaces/{workspace_id}/inspect",
    response_model=WorkspaceInspection,
)
def inspect_workspace(workspace_id: str, current_user: str = Depends(require_auth)):
    svc = _service()
    try:
        updated, inspection = svc.inspect(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail="Workspace not found")
    audit_writer.write(
        "workspace_inspected",
        "workspace",
        updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={
            "status": updated.status,
            "exists": inspection.exists,
            "is_directory": inspection.is_directory,
            "is_git_repo": inspection.is_git_repo,
            "blocked_path_hits_count": len(inspection.blocked_path_hits),
        },
    )
    return inspection


@router.post("/workspaces/{workspace_id}/archive", response_model=Workspace)
def archive_workspace(workspace_id: str, current_user: str = Depends(require_auth)):
    svc = _service()
    try:
        updated = svc.archive(workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail="Workspace not found")
    audit_writer.write(
        "workspace_archived",
        "workspace",
        updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"workspace_type": updated.workspace_type},
    )
    return updated
