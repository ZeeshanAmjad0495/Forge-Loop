from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..models import (
    GitCommitCreate,
    GitCommitRecord,
    GitInspectionResponse,
    WorkspaceBranch,
    WorkspaceBranchCreate,
    WorkspaceBranchResponse,
)
from ..services import git_workflow

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/git/inspect",
    response_model=GitInspectionResponse,
)
def inspect_workspace_git(
    workspace_id: str,
    current_user: str = Depends(require_auth),
):
    return git_workflow.inspect(workspace_id, current_user)


@router.post(
    "/workspaces/{workspace_id}/branches",
    response_model=WorkspaceBranchResponse,
    status_code=201,
)
def create_workspace_branch(
    workspace_id: str,
    body: WorkspaceBranchCreate,
    current_user: str = Depends(require_auth),
):
    return git_workflow.create_branch(workspace_id, body, current_user)


@router.get(
    "/workspaces/{workspace_id}/branches",
    response_model=list[WorkspaceBranch],
)
def list_workspace_branches(
    workspace_id: str,
    current_user: str = Depends(require_auth),
):
    return git_workflow.list_branches(workspace_id, current_user)


@router.get(
    "/workspace-branches/{branch_id}",
    response_model=WorkspaceBranchResponse,
)
def get_workspace_branch(
    branch_id: str,
    current_user: str = Depends(require_auth),
):
    return git_workflow.get_branch(branch_id, current_user)


@router.post(
    "/workspace-branches/{branch_id}/inspect",
    response_model=WorkspaceBranchResponse,
)
def inspect_workspace_branch(
    branch_id: str,
    current_user: str = Depends(require_auth),
):
    return git_workflow.inspect_branch(branch_id, current_user)


@router.post(
    "/workspace-branches/{branch_id}/commit",
    response_model=GitCommitRecord,
    status_code=201,
)
def create_workspace_commit(
    branch_id: str,
    body: GitCommitCreate,
    current_user: str = Depends(require_auth),
):
    return git_workflow.commit(branch_id, body, current_user)


@router.get(
    "/workspace-branches/{branch_id}/commits",
    response_model=list[GitCommitRecord],
)
def list_workspace_commits(
    branch_id: str,
    current_user: str = Depends(require_auth),
):
    return git_workflow.list_commits(branch_id, current_user)
