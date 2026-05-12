from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

BackupExportType = Literal[
    "project",
    "full_metadata",
    "selected_entities",
    "audit_only",
    "templates_only",
    "custom",
]
BackupExportStatus = Literal["requested", "completed", "failed", "archived"]
BackupExportFormat = Literal["json"]


class BackupExportCreate(BaseModel):
    export_type: BackupExportType = "project"
    project_id: str | None = None
    format: BackupExportFormat = "json"
    scope: list[str] = []


class BackupExport(BaseModel):
    id: str
    project_id: str | None = None
    export_type: BackupExportType = "project"
    status: BackupExportStatus = "requested"
    format: BackupExportFormat = "json"
    scope: list[str] = []
    artifact_id: str | None = None
    summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


# -- Import ---------------------------------------------------------------

BackupImportMode = Literal["dry_run", "create_new", "merge_skip_existing"]
BackupImportStatus = Literal[
    "requested",
    "completed",
    "failed",
    "cancelled",
]


class BackupImportCreate(BaseModel):
    project_id: str | None = None
    source_artifact_id: str | None = None
    mode: BackupImportMode = "dry_run"
    bundle: dict[str, Any] | None = None


class BackupImport(BaseModel):
    id: str
    project_id: str | None = None
    source_artifact_id: str | None = None
    mode: BackupImportMode = "dry_run"
    status: BackupImportStatus = "requested"
    summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
