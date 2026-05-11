"""Workspace service layer.

Pathlib-only. No subprocess, no shell, no git, no GitHub, no network, no LLM,
no Firestore. Routes call this layer; the layer calls the repository
abstractions and the workspace_paths helper.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..models import (
    Workspace,
    WorkspaceCreate,
    WorkspaceInspection,
    WorkspaceUpdate,
)
from . import workspace_paths
from .workspace_paths import WorkspacePathError


class WorkspaceNotFound(LookupError):
    pass


class ProjectNotFound(LookupError):
    pass


class CodeRepositoryNotFound(LookupError):
    pass


class WorkspaceValidationError(ValueError):
    pass


@dataclass
class WorkspaceService:
    workspace_repo: object
    project_repo: object
    code_repo_repo: object
    repo_safety_profile_repo: object

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_project(self, project_id: str) -> None:
        if self.project_repo.get(project_id) is None:
            raise ProjectNotFound(project_id)

    def _require_code_repository(self, project_id: str, code_repository_id: str) -> None:
        repo_obj = self.code_repo_repo.get(code_repository_id)
        if repo_obj is None or repo_obj.project_id != project_id:
            raise CodeRepositoryNotFound(code_repository_id)

    def create(self, project_id: str, body: WorkspaceCreate) -> Workspace:
        self._require_project(project_id)
        if body.code_repository_id:
            self._require_code_repository(project_id, body.code_repository_id)

        workspace_id = str(uuid.uuid4())
        allow_outside = config.WORKSPACE_ALLOW_OUTSIDE_ROOT
        wtype = body.workspace_type
        now = self._now()

        resolved_path: Path
        status: str
        error_message: str | None = None

        if wtype == "local_created":
            if body.root_path:
                resolved_path = workspace_paths.validate_and_resolve_path(
                    body.root_path, allow_outside_root=allow_outside
                )
            else:
                resolved_path = workspace_paths.default_created_path(project_id, workspace_id)
            if body.create_directory:
                try:
                    resolved_path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    raise WorkspaceValidationError(
                        f"could not create directory: {exc}"
                    ) from exc
            status = "ready" if resolved_path.is_dir() else "registered"

        elif wtype == "local_existing":
            if not body.root_path:
                raise WorkspaceValidationError("root_path is required for local_existing")
            resolved_path = workspace_paths.validate_and_resolve_path(
                body.root_path, allow_outside_root=allow_outside
            )
            if not resolved_path.exists():
                status = "missing"
                error_message = "Path does not exist"
            elif resolved_path.is_dir():
                status = "ready"
            else:
                status = "invalid"
                error_message = "Path is not a directory"

        elif wtype == "git_clone_pending":
            if body.root_path:
                resolved_path = workspace_paths.validate_and_resolve_path(
                    body.root_path, allow_outside_root=allow_outside
                )
            else:
                resolved_path = workspace_paths.default_created_path(project_id, workspace_id)
            status = "registered"

        elif wtype == "manual":
            resolved_path = workspace_paths.validate_and_resolve_path(
                body.root_path, allow_outside_root=allow_outside
            )
            status = "registered"

        else:
            raise WorkspaceValidationError(f"unknown workspace_type: {wtype}")

        workspace = Workspace(
            id=workspace_id,
            project_id=project_id,
            code_repository_id=body.code_repository_id,
            name=body.name,
            root_path=str(resolved_path),
            workspace_type=wtype,
            status=status,
            description=body.description,
            created_at=now,
            updated_at=now,
            last_inspected_at=None,
            error_message=error_message,
        )
        self.workspace_repo.save(workspace)
        return workspace

    def get(self, workspace_id: str) -> Workspace:
        w = self.workspace_repo.get(workspace_id)
        if w is None:
            raise WorkspaceNotFound(workspace_id)
        return w

    def list_by_project(self, project_id: str) -> list[Workspace]:
        self._require_project(project_id)
        return self.workspace_repo.list_by_project(project_id)

    def update(self, workspace_id: str, body: WorkspaceUpdate) -> Workspace:
        workspace = self.get(workspace_id)
        updates = body.model_dump(exclude_unset=True)
        if body.code_repository_id is not None:
            self._require_code_repository(workspace.project_id, body.code_repository_id)
        updates["updated_at"] = self._now()
        updated = workspace.model_copy(update=updates)
        self.workspace_repo.update(updated)
        return updated

    def inspect(self, workspace_id: str) -> tuple[Workspace, WorkspaceInspection]:
        workspace = self.get(workspace_id)
        blocked_paths: list[str] = []
        if workspace.code_repository_id:
            profile = self.repo_safety_profile_repo.get_by_repo(workspace.code_repository_id)
            if profile is not None:
                blocked_paths = list(profile.blocked_paths)
        result = workspace_paths.inspect_path(Path(workspace.root_path), blocked_paths)
        inspection = WorkspaceInspection(workspace_id=workspace.id, **result)

        now = self._now()
        new_status = workspace.status
        new_error = workspace.error_message
        if workspace.status != "archived":
            if not inspection.exists:
                new_status = "missing"
                new_error = "Path does not exist"
            elif not inspection.is_directory:
                new_status = "invalid"
                new_error = "Path is not a directory"
            else:
                new_status = "ready"
                new_error = None

        updated = workspace.model_copy(
            update={
                "last_inspected_at": now,
                "updated_at": now,
                "status": new_status,
                "error_message": new_error,
            }
        )
        self.workspace_repo.update(updated)
        return updated, inspection

    def archive(self, workspace_id: str) -> Workspace:
        workspace = self.get(workspace_id)
        now = self._now()
        updated = workspace.model_copy(update={"status": "archived", "updated_at": now})
        self.workspace_repo.update(updated)
        return updated


__all__ = [
    "WorkspaceService",
    "WorkspaceNotFound",
    "ProjectNotFound",
    "CodeRepositoryNotFound",
    "WorkspaceValidationError",
    "WorkspacePathError",
]
