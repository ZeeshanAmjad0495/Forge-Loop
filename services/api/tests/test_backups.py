import json

import pytest

from app.models import BackupExportCreate, BackupImportCreate
from app.repositories_state import repos
from app.services.backup_export import (
    SCHEMA_VERSION,
    export_bundle,
    import_bundle,
)


# -- service unit tests ---------------------------------------------------


def _make_project(client, name: str = "TestProject"):
    res = client.post(
        "/projects",
        json={"name": name, "description": "fixture project"},
    )
    assert res.status_code == 201
    return res.json()


def test_export_project_bundle_contains_schema_and_counts(client):
    project = _make_project(client)
    record, artifact, bundle = export_bundle(
        repos,
        repos.backup_export,
        repos.artifact,
        body=BackupExportCreate(
            export_type="project", project_id=project["id"]
        ),
    )
    assert record.status == "completed"
    assert record.artifact_id == artifact.id
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["project_id"] == project["id"]
    assert "entity_counts" in bundle
    assert bundle["entity_counts"]["projects"] == 1


def test_export_project_requires_project_id():
    with pytest.raises(ValueError):
        export_bundle(
            repos,
            repos.backup_export,
            repos.artifact,
            body=BackupExportCreate(export_type="project"),
        )


def test_export_omits_sensitive_fields(client):
    project = _make_project(client)
    # Add a code repository with a token-like field via project context update
    # (project_contexts don't have api_key, so we directly create one through the
    # code_repository repo to make sure no token leaks; for now we assert that
    # the redaction helper drops any *secret*/api_key keys from arbitrary dicts.)
    from app.services.backup_export import _redact

    redacted = _redact({"id": "x", "api_key": "shh", "github_token": "tok"})
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["github_token"] == "[REDACTED]"
    assert redacted["id"] == "x"


def test_dry_run_import_validates_and_reports_counts(client):
    project = _make_project(client)
    _record, _artifact, bundle = export_bundle(
        repos,
        repos.backup_export,
        repos.artifact,
        body=BackupExportCreate(
            export_type="project", project_id=project["id"]
        ),
    )
    dry = import_bundle(
        repos,
        repos.backup_import,
        repos.artifact,
        body=BackupImportCreate(mode="dry_run", bundle=bundle),
    )
    assert dry.status == "completed"
    assert dry.summary["validation_errors"] == []
    assert "would_import" in dry.summary["plan"]


def test_dry_run_rejects_bad_schema_version(client):
    dry = import_bundle(
        repos,
        repos.backup_import,
        repos.artifact,
        body=BackupImportCreate(
            mode="dry_run",
            bundle={"schema_version": 99, "entities": {}},
        ),
    )
    assert dry.status == "completed"
    assert any(
        "schema_version" in e for e in dry.summary["validation_errors"]
    )


def test_create_new_import_skips_existing(client):
    project = _make_project(client)
    _record, _artifact, bundle = export_bundle(
        repos,
        repos.backup_export,
        repos.artifact,
        body=BackupExportCreate(
            export_type="project", project_id=project["id"]
        ),
    )
    # importing back into the same store should skip the existing project
    record = import_bundle(
        repos,
        repos.backup_import,
        repos.artifact,
        body=BackupImportCreate(mode="create_new", bundle=bundle),
    )
    assert record.status == "completed"
    imported_projects = record.summary["imported"].get("projects", 0)
    skipped_projects = record.summary["skipped_existing"].get("projects", 0)
    assert imported_projects == 0
    assert skipped_projects == 1


def test_create_new_import_creates_missing(client):
    project = _make_project(client)
    _record, _artifact, bundle = export_bundle(
        repos,
        repos.backup_export,
        repos.artifact,
        body=BackupExportCreate(
            export_type="project", project_id=project["id"]
        ),
    )
    # Clear repos so the project is "missing", then re-import
    repos.reset_all()
    record = import_bundle(
        repos,
        repos.backup_import,
        repos.artifact,
        body=BackupImportCreate(mode="create_new", bundle=bundle),
    )
    assert record.status == "completed"
    assert record.summary["imported"].get("projects", 0) == 1
    assert repos.project.get(project["id"]) is not None


def test_import_invalid_artifact_id_fails(client):
    record = import_bundle(
        repos,
        repos.backup_import,
        repos.artifact,
        body=BackupImportCreate(
            mode="dry_run", source_artifact_id="missing"
        ),
    )
    assert record.status == "failed"
    assert record.error_message


# -- API tests ------------------------------------------------------------


def test_create_export_via_api(client):
    project = _make_project(client)
    res = client.post(
        "/backups/exports",
        json={"export_type": "project", "project_id": project["id"]},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "completed"
    assert body["artifact_id"] is not None


def test_create_export_project_without_project_id_400(client):
    res = client.post(
        "/backups/exports",
        json={"export_type": "project"},
    )
    assert res.status_code == 400


def test_export_full_metadata_via_api(client):
    _make_project(client)
    res = client.post(
        "/backups/exports", json={"export_type": "full_metadata"}
    )
    assert res.status_code == 201
    assert res.json()["status"] == "completed"


def test_list_and_get_backup_exports(client):
    project = _make_project(client)
    created = client.post(
        "/backups/exports",
        json={"export_type": "project", "project_id": project["id"]},
    ).json()

    listed = client.get(
        f"/projects/{project['id']}/backups/exports"
    ).json()
    assert len(listed) == 1
    fetched = client.get(f"/backups/exports/{created['id']}").json()
    assert fetched["id"] == created["id"]


def test_dry_run_import_via_api(client):
    project = _make_project(client)
    export = client.post(
        "/backups/exports",
        json={"export_type": "project", "project_id": project["id"]},
    ).json()

    res = client.post(
        "/backups/imports/dry-run",
        json={"source_artifact_id": export["artifact_id"]},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "completed"


def test_full_import_rejects_dry_run_mode(client):
    res = client.post(
        "/backups/imports",
        json={"mode": "dry_run", "bundle": {"schema_version": 1, "entities": {}}},
    )
    assert res.status_code == 400


def test_full_create_new_import_via_api(client):
    project = _make_project(client)
    export = client.post(
        "/backups/exports",
        json={"export_type": "project", "project_id": project["id"]},
    ).json()
    res = client.post(
        "/backups/imports",
        json={
            "mode": "create_new",
            "source_artifact_id": export["artifact_id"],
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "completed"


def test_get_unknown_export_404(client):
    res = client.get("/backups/exports/missing")
    assert res.status_code == 404
