"""Filesystem snapshot helpers for OpenHands execution change tracking.

Pathlib-only. No subprocess, no git, no shell, no network, no file content
reads. Records per-file (mtime_ns, size); diffs two snapshots to surface
added/modified/deleted relative paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

DEFAULT_EXCLUDES: frozenset[str] = frozenset({
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".forgeloop",
})

DEFAULT_FILE_LIMIT = 20000


@dataclass(frozen=True)
class FileMeta:
    mtime_ns: int
    size: int


@dataclass
class WorkspaceSnapshot:
    files: dict[str, FileMeta]
    truncated: bool


@dataclass(frozen=True)
class ChangedPath:
    path: str
    change_type: str  # "added" | "modified" | "deleted"


@dataclass
class WorkspaceDiff:
    added: list[ChangedPath]
    modified: list[ChangedPath]
    deleted: list[ChangedPath]
    blocked_path_changes: list[str]

    def all_changes(self) -> list[ChangedPath]:
        return [*self.added, *self.modified, *self.deleted]


def _normalize_blocked_prefixes(blocked_paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in blocked_paths or []:
        name = (raw or "").strip().rstrip("/")
        if not name:
            continue
        parts = PurePosixPath(name).parts
        if any(p in ("..", "") for p in parts):
            continue
        out.append(name)
    return out


def _is_blocked(rel_posix: str, blocked_prefixes: list[str]) -> bool:
    for prefix in blocked_prefixes:
        if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
            return True
    return False


def snapshot(
    root: Path,
    *,
    blocked_paths: Iterable[str] | None = None,
    file_limit: int = DEFAULT_FILE_LIMIT,
    excludes: Iterable[str] | None = None,
) -> WorkspaceSnapshot:
    """Walk ``root`` and record file metadata.

    Returns ``WorkspaceSnapshot.truncated=True`` if the file count limit was
    reached. Symlinks are not followed. Blocked paths from the safety profile
    are *included* in the snapshot so that post-execution diffs can flag
    illegal writes; ``DEFAULT_EXCLUDES`` (heavy/derived dirs) are skipped.
    """
    exclude_set = frozenset(excludes) if excludes is not None else DEFAULT_EXCLUDES
    files: dict[str, FileMeta] = {}
    truncated = False
    if not root.exists() or not root.is_dir():
        return WorkspaceSnapshot(files=files, truncated=False)

    root_resolved = root.resolve()
    stack: list[Path] = [root_resolved]
    while stack:
        current = stack.pop()
        try:
            it = os.scandir(current)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue
        with it:
            for entry in it:
                if len(files) >= file_limit:
                    truncated = True
                    break
                name = entry.name
                if name in exclude_set:
                    continue
                try:
                    is_symlink = entry.is_symlink()
                except OSError:
                    continue
                if is_symlink:
                    continue
                entry_path = Path(entry.path)
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry_path)
                        continue
                except OSError:
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                try:
                    rel = entry_path.relative_to(root_resolved)
                except ValueError:
                    continue
                rel_posix = PurePosixPath(*rel.parts).as_posix()
                files[rel_posix] = FileMeta(mtime_ns=stat.st_mtime_ns, size=stat.st_size)
        if truncated:
            break

    return WorkspaceSnapshot(files=files, truncated=truncated)


def diff(
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
    *,
    blocked_paths: Iterable[str] | None = None,
) -> WorkspaceDiff:
    """Compute added/modified/deleted between two snapshots.

    Modified = same path, different (mtime_ns, size). Blocked-path changes are
    any added/modified/deleted entries whose relative path starts with a
    safety-profile blocked-path prefix.
    """
    before_files = before.files
    after_files = after.files
    added: list[ChangedPath] = []
    modified: list[ChangedPath] = []
    deleted: list[ChangedPath] = []

    for path, meta in after_files.items():
        prev = before_files.get(path)
        if prev is None:
            added.append(ChangedPath(path=path, change_type="added"))
        elif prev != meta:
            modified.append(ChangedPath(path=path, change_type="modified"))

    for path in before_files.keys():
        if path not in after_files:
            deleted.append(ChangedPath(path=path, change_type="deleted"))

    blocked_prefixes = _normalize_blocked_prefixes(blocked_paths or [])
    blocked_changes: list[str] = []
    if blocked_prefixes:
        for change in (*added, *modified, *deleted):
            if _is_blocked(change.path, blocked_prefixes):
                blocked_changes.append(change.path)

    added.sort(key=lambda c: c.path)
    modified.sort(key=lambda c: c.path)
    deleted.sort(key=lambda c: c.path)
    blocked_changes.sort()
    return WorkspaceDiff(
        added=added,
        modified=modified,
        deleted=deleted,
        blocked_path_changes=blocked_changes,
    )


__all__ = [
    "DEFAULT_EXCLUDES",
    "DEFAULT_FILE_LIMIT",
    "FileMeta",
    "WorkspaceSnapshot",
    "ChangedPath",
    "WorkspaceDiff",
    "snapshot",
    "diff",
]
