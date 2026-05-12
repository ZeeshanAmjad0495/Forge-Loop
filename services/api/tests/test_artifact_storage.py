"""Tests for Release 8 Task 43 — filesystem artifact storage service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import config
from app.services import artifact_storage


def _now() -> datetime:
    return datetime(2026, 5, 12, 3, 11, tzinfo=timezone.utc)


def _configure_filesystem(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "filesystem")
    monkeypatch.setattr(config, "ARTIFACT_FILESYSTEM_ROOT", str(tmp_path))


def test_database_provider_preserves_existing_inline_behavior():
    art = artifact_storage.store_artifact(
        artifact_id="a1",
        artifact_type="command_run_output",
        content="hello world",
        created_at=_now(),
        project_id="p1",
    )
    assert art.storage_provider == "database"
    assert art.content == "hello world"
    assert art.storage_path is None
    assert art.content_size_bytes == len(b"hello world")
    assert art.content_sha256 == hashlib.sha256(b"hello world").hexdigest()


def test_filesystem_provider_writes_file_under_root(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    art = artifact_storage.store_artifact(
        artifact_id="a2",
        artifact_type="command_run_output",
        content="filesystem-backed",
        created_at=_now(),
        project_id="proj-1",
    )
    assert art.storage_provider == "filesystem"
    assert art.storage_path is not None
    assert art.content == ""
    written = tmp_path / "proj-1" / "a2.txt"
    assert written.exists()
    assert written.read_text(encoding="utf-8") == "filesystem-backed"


def test_filesystem_provider_records_size_and_hash(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    payload = "abc-payload-123"
    art = artifact_storage.store_artifact(
        artifact_id="a3",
        artifact_type="command_run_output",
        content=payload,
        created_at=_now(),
        project_id="proj-1",
    )
    assert art.content_size_bytes == len(payload.encode("utf-8"))
    assert art.content_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_filesystem_provider_uses_global_subdir_when_no_project(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    art = artifact_storage.store_artifact(
        artifact_id="a4",
        artifact_type="command_run_output",
        content="x",
        created_at=_now(),
        project_id=None,
    )
    assert art.storage_path == str(Path("_global") / "a4.txt")


def test_read_artifact_content_inline_returns_content(monkeypatch, tmp_path):
    art = artifact_storage.store_artifact(
        artifact_id="a5",
        artifact_type="command_run_output",
        content="inline-data",
        created_at=_now(),
        project_id="p1",
    )
    assert artifact_storage.read_artifact_content(art) == "inline-data"


def test_read_artifact_content_filesystem_reads_from_disk(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    art = artifact_storage.store_artifact(
        artifact_id="a6",
        artifact_type="command_run_output",
        content="disk-data",
        created_at=_now(),
        project_id="p1",
    )
    assert artifact_storage.read_artifact_content(art) == "disk-data"


def test_path_traversal_in_artifact_id_rejected(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    with pytest.raises(artifact_storage.ArtifactStorageError):
        artifact_storage.store_artifact(
            artifact_id="../escape",
            artifact_type="command_run_output",
            content="x",
            created_at=_now(),
            project_id="p1",
        )


def test_path_traversal_in_project_id_rejected(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    with pytest.raises(artifact_storage.ArtifactStorageError):
        artifact_storage.store_artifact(
            artifact_id="ok",
            artifact_type="command_run_output",
            content="x",
            created_at=_now(),
            project_id="../escape",
        )


def test_read_outside_root_rejected(monkeypatch, tmp_path):
    _configure_filesystem(monkeypatch, tmp_path)
    # Build a synthetic Artifact pointing outside the root.
    from app.models import Artifact

    outside = tmp_path.parent / "evil.txt"
    outside.write_text("nope")
    art = Artifact(
        id="evil",
        artifact_type="command_run_output",
        content="",
        created_at=_now(),
        storage_provider="filesystem",
        storage_path=str(outside),
    )
    with pytest.raises(artifact_storage.ArtifactStorageError):
        artifact_storage.read_artifact_content(art)
