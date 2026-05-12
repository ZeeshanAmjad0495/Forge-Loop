from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    BackupExport,
    BackupExportCreate,
    BackupImport,
    BackupImportCreate,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    backup_export_repo,
    backup_import_repo,
    project_repo,
    repos,
)
from ..services.backup_export import (
    SCHEMA_VERSION,
    export_bundle,
    import_bundle,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/backups/exports", response_model=BackupExport, status_code=201)
def create_backup_export(
    body: BackupExportCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    if body.export_type == "project" and body.project_id is None:
        raise HTTPException(
            status_code=400,
            detail="project_id is required for export_type='project'",
        )
    try:
        record, _artifact, _bundle = export_bundle(
            repos,
            backup_export_repo,
            artifact_repo,
            body=body,
        )
    except ValueError as exc:
        audit_writer.write(
            action="backup_export_failed",
            target_type="backup_export",
            target_id="failed",
            project_id=body.project_id,
            actor_email=current_user,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc))
    audit_writer.write(
        action="backup_export_requested",
        target_type="backup_export",
        target_id=record.id,
        project_id=record.project_id,
        actor_email=current_user,
        details={"export_type": record.export_type},
    )
    audit_writer.write(
        action="backup_export_completed",
        target_type="backup_export",
        target_id=record.id,
        project_id=record.project_id,
        actor_email=current_user,
        details={"schema_version": SCHEMA_VERSION},
    )
    return record


@router.get("/backups/exports", response_model=list[BackupExport])
def list_backup_exports(
    project_id: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    if project_id is not None:
        _ensure_project(project_id)
        items = backup_export_repo.list_by_project(project_id)
    else:
        items = backup_export_repo.list_all()
    if status is not None:
        items = [e for e in items if e.status == status]
    return items


@router.get(
    "/projects/{project_id}/backups/exports",
    response_model=list[BackupExport],
)
def list_project_backup_exports(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    return backup_export_repo.list_by_project(project_id)


@router.get("/backups/exports/{export_id}", response_model=BackupExport)
def get_backup_export(
    export_id: str, current_user: str = Depends(require_auth)
):
    record = backup_export_repo.get(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Backup export not found")
    return record


@router.post(
    "/backups/imports/dry-run", response_model=BackupImport, status_code=201
)
def dry_run_import(
    body: BackupImportCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    payload = body.model_copy(update={"mode": "dry_run"})
    record = import_bundle(
        repos,
        backup_import_repo,
        artifact_repo,
        body=payload,
    )
    audit_writer.write(
        action="backup_import_dry_run_completed",
        target_type="backup_import",
        target_id=record.id,
        project_id=record.project_id,
        actor_email=current_user,
        details={"status": record.status},
    )
    return record


@router.post("/backups/imports", response_model=BackupImport, status_code=201)
def import_backup(
    body: BackupImportCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    if body.mode == "dry_run":
        raise HTTPException(
            status_code=400,
            detail="Use /backups/imports/dry-run for dry_run mode",
        )
    record = import_bundle(
        repos,
        backup_import_repo,
        artifact_repo,
        body=body,
    )
    action = (
        "backup_import_completed"
        if record.status == "completed"
        else "backup_import_failed"
    )
    audit_writer.write(
        action=action,
        target_type="backup_import",
        target_id=record.id,
        project_id=record.project_id,
        actor_email=current_user,
        details={"mode": record.mode, "status": record.status},
    )
    return record


@router.get("/backups/imports/{import_id}", response_model=BackupImport)
def get_backup_import(
    import_id: str, current_user: str = Depends(require_auth)
):
    record = backup_import_repo.get(import_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Backup import not found")
    return record
