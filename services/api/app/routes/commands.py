from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    CommandDefinition,
    CommandDefinitionCreate,
    CommandDefinitionUpdate,
    CommandRun,
    CommandRunCreate,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    code_repo_repo,
    command_definition_repo,
    command_run_repo,
    project_repo,
    workspace_repo,
)
from ..services.command_runner import (
    CodeRepositoryNotFoundError,
    CommandDefinitionNotFound,
    CommandRunNotFound,
    CommandRunnerDisabled,
    CommandRunnerService,
    CommandValidationError,
    ProjectNotFoundError,
    WorkspaceNotFoundError,
)

router = APIRouter()


def _service() -> CommandRunnerService:
    return CommandRunnerService(
        command_def_repo=command_definition_repo,
        command_run_repo=command_run_repo,
        project_repo=project_repo,
        workspace_repo=workspace_repo,
        code_repo_repo=code_repo_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
    )


@router.post(
    "/projects/{project_id}/command-definitions",
    response_model=CommandDefinition,
    status_code=201,
)
def create_command_definition(
    project_id: str,
    body: CommandDefinitionCreate,
    current_user: str = Depends(require_auth),
):
    svc = _service()
    try:
        return svc.create_definition(project_id, body, actor_email=current_user)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except CodeRepositoryNotFoundError:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    except CommandValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/projects/{project_id}/command-definitions",
    response_model=list[CommandDefinition],
)
def list_project_command_definitions(
    project_id: str, _: str = Depends(require_auth)
):
    svc = _service()
    try:
        return svc.list_definitions_by_project(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get(
    "/command-definitions/{command_definition_id}",
    response_model=CommandDefinition,
)
def get_command_definition(
    command_definition_id: str, _: str = Depends(require_auth)
):
    svc = _service()
    try:
        return svc.get_definition(command_definition_id)
    except CommandDefinitionNotFound:
        raise HTTPException(status_code=404, detail="CommandDefinition not found")


@router.patch(
    "/command-definitions/{command_definition_id}",
    response_model=CommandDefinition,
)
def update_command_definition(
    command_definition_id: str,
    body: CommandDefinitionUpdate,
    current_user: str = Depends(require_auth),
):
    svc = _service()
    try:
        return svc.update_definition(
            command_definition_id, body, actor_email=current_user
        )
    except CommandDefinitionNotFound:
        raise HTTPException(status_code=404, detail="CommandDefinition not found")
    except CommandValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/workspaces/{workspace_id}/command-runs",
    response_model=CommandRun,
    status_code=201,
)
def create_command_run(
    workspace_id: str,
    body: CommandRunCreate,
    current_user: str = Depends(require_auth),
):
    svc = _service()
    try:
        return svc.run(workspace_id, body, actor_email=current_user)
    except CommandRunnerDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except CommandDefinitionNotFound:
        raise HTTPException(status_code=404, detail="CommandDefinition not found")
    except CommandValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/workspaces/{workspace_id}/command-runs",
    response_model=list[CommandRun],
)
def list_workspace_command_runs(
    workspace_id: str, _: str = Depends(require_auth)
):
    svc = _service()
    try:
        return svc.list_runs_by_workspace(workspace_id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.get(
    "/projects/{project_id}/command-runs",
    response_model=list[CommandRun],
)
def list_project_command_runs(project_id: str, _: str = Depends(require_auth)):
    svc = _service()
    try:
        return svc.list_runs_by_project(project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/command-runs/{command_run_id}", response_model=CommandRun)
def get_command_run(command_run_id: str, _: str = Depends(require_auth)):
    svc = _service()
    try:
        return svc.get_run(command_run_id)
    except CommandRunNotFound:
        raise HTTPException(status_code=404, detail="CommandRun not found")
