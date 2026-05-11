from datetime import datetime
from typing import Literal

from pydantic import BaseModel

WorkspaceType = Literal["local_existing", "local_created", "git_clone_pending", "manual"]
WorkspaceStatus = Literal["registered", "ready", "missing", "invalid", "archived"]


class WorkspaceCreate(BaseModel):
    code_repository_id: str | None = None
    name: str
    root_path: str | None = None
    workspace_type: WorkspaceType = "local_created"
    description: str | None = None
    create_directory: bool = True


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: WorkspaceStatus | None = None
    code_repository_id: str | None = None


class Workspace(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    name: str
    root_path: str
    workspace_type: WorkspaceType
    status: WorkspaceStatus
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    last_inspected_at: datetime | None = None
    error_message: str | None = None


class WorkspaceInspection(BaseModel):
    workspace_id: str
    exists: bool
    is_directory: bool
    is_git_repo: bool
    current_branch: str | None = None
    dirty: bool = False
    file_count_estimate: int = 0
    blocked_path_hits: list[str] = []
    notes: list[str] = []
