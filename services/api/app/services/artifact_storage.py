"""Artifact storage service (Release 8, Task 43).

Provides a single helper to persist Artifact *content* either inline in the
database (existing behavior) or on the local filesystem under
``ARTIFACT_FILESYSTEM_ROOT``. Repository layer remains responsible for
Artifact *metadata*.

Filesystem writes are constrained to the configured root via a resolved
path check (defence against traversal).
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from .. import config
from ..models import Artifact


class ArtifactStorageError(RuntimeError):
    """Raised when artifact storage cannot honor a request."""


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _resolve_root() -> Path:
    """Return the resolved filesystem root, creating it if needed."""
    root = Path(config.ARTIFACT_FILESYSTEM_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _artifact_filename(artifact_id: str) -> str:
    """Return a safe filename for an artifact id. Refuses traversal/path chars."""
    if not artifact_id or any(ch in artifact_id for ch in ("/", "\\", "..", "\0")):
        raise ArtifactStorageError(f"Unsafe artifact id: {artifact_id!r}")
    return f"{artifact_id}.txt"


def _artifact_subdir(project_id: str | None) -> str:
    if not project_id:
        return "_global"
    if any(ch in project_id for ch in ("/", "\\", "..", "\0")):
        raise ArtifactStorageError(f"Unsafe project_id for storage path: {project_id!r}")
    return project_id


def _filesystem_write(content: str, *, artifact_id: str, project_id: str | None) -> Path:
    root = _resolve_root()
    target_dir = root / _artifact_subdir(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / _artifact_filename(artifact_id)).resolve()
    # Defence-in-depth: ensure the resolved path is still under root.
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArtifactStorageError(
            f"Refusing to write artifact outside ARTIFACT_FILESYSTEM_ROOT: {target}"
        ) from exc
    target.write_text(content, encoding="utf-8")
    return target


def _filesystem_read(storage_path: str) -> str:
    root = _resolve_root()
    candidate = Path(storage_path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ArtifactStorageError(
            f"Refusing to read artifact outside ARTIFACT_FILESYSTEM_ROOT: {candidate}"
        ) from exc
    return candidate.read_text(encoding="utf-8")


def store_artifact(
    *,
    artifact_id: str,
    artifact_type: str,
    content: str,
    created_at: datetime,
    ticket_id: str | None = None,
    requirement_id: str | None = None,
    agent_run_id: str | None = None,
    project_id: str | None = None,
) -> Artifact:
    """Build an Artifact, persisting its content according to the configured provider.

    Returns the Artifact model; the caller is responsible for saving it via
    the appropriate repository.
    """
    size = len(content.encode("utf-8"))
    digest = _sha256(content)

    provider = config.ARTIFACT_STORAGE_PROVIDER
    if provider == "filesystem":
        path = _filesystem_write(
            content, artifact_id=artifact_id, project_id=project_id
        )
        rel_path = _relative_to_root(path)
        # Keep `content` empty for filesystem-backed artifacts; readers must
        # use ``read_artifact_content`` to fetch the body.
        return Artifact(
            id=artifact_id,
            ticket_id=ticket_id,
            requirement_id=requirement_id,
            agent_run_id=agent_run_id,
            artifact_type=artifact_type,  # type: ignore[arg-type]
            content="",
            created_at=created_at,
            storage_provider="filesystem",
            storage_path=rel_path,
            content_size_bytes=size,
            content_sha256=digest,
        )

    # Default: database / inline content
    return Artifact(
        id=artifact_id,
        ticket_id=ticket_id,
        requirement_id=requirement_id,
        agent_run_id=agent_run_id,
        artifact_type=artifact_type,  # type: ignore[arg-type]
        content=content,
        created_at=created_at,
        storage_provider="database",
        content_size_bytes=size,
        content_sha256=digest,
    )


def _relative_to_root(path: Path) -> str:
    root = _resolve_root()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_artifact_content(artifact: Artifact) -> str:
    """Return the content of an Artifact regardless of where it is stored."""
    if artifact.storage_provider == "filesystem" and artifact.storage_path:
        root = _resolve_root()
        # Storage paths are written relative to root; absolute paths are
        # accepted for backward compatibility but still checked.
        candidate = Path(artifact.storage_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        return _filesystem_read(str(candidate))
    return artifact.content
