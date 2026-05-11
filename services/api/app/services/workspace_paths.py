"""Safe filesystem helpers for the Workspace feature.

Pathlib-only. No subprocess, no shell, no network, no git, no file content reads.
"""

from __future__ import annotations

import os
from pathlib import Path

from .. import config


class WorkspacePathError(ValueError):
    """Raised when a requested workspace path fails safety validation."""


_DANGEROUS_ROOTS_LITERAL = ("/", "/etc", "/usr", "/var", "/bin", "/sbin")
_FILE_COUNT_LIMIT = 1000


def resolve_workspace_root() -> Path:
    return Path(config.FORGELOOP_WORKSPACE_ROOT).expanduser().resolve()


def _dangerous_targets() -> set[Path]:
    targets: set[Path] = {Path(p).resolve() for p in _DANGEROUS_ROOTS_LITERAL}
    targets.add(Path.home().resolve())
    targets.add(Path.cwd().resolve())
    return targets


def validate_and_resolve_path(raw: str | None, *, allow_outside_root: bool) -> Path:
    if raw is None or not str(raw).strip():
        raise WorkspacePathError("root_path is empty")
    candidate = Path(str(raw).strip()).expanduser()
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise WorkspacePathError(f"could not resolve path: {exc}") from exc

    if resolved in _dangerous_targets():
        raise WorkspacePathError("path matches a protected system location")

    if not allow_outside_root:
        root = resolve_workspace_root()
        if not resolved.is_relative_to(root):
            raise WorkspacePathError(
                "path is outside the configured workspace root and "
                "WORKSPACE_ALLOW_OUTSIDE_ROOT is false"
            )
    return resolved


def default_created_path(project_id: str, workspace_id: str) -> Path:
    return (resolve_workspace_root() / project_id / workspace_id).resolve()


def inspect_path(path: Path, blocked_paths: list[str] | None = None) -> dict:
    """Pathlib-only inspection. Returns a dict matching WorkspaceInspection fields
    minus ``workspace_id`` (caller fills that in).
    """
    blocked_paths = blocked_paths or []
    exists = path.exists()
    is_directory = path.is_dir() if exists else False
    is_git_repo = (path / ".git").exists() if is_directory else False

    notes: list[str] = []
    if not exists:
        notes.append("path missing")
    elif not is_directory:
        notes.append("path is a file, not a directory")
    if is_git_repo:
        notes.append(".git directory present")

    file_count_estimate = 0
    if is_directory:
        file_count_estimate = _bounded_count(path)
        if file_count_estimate >= _FILE_COUNT_LIMIT:
            notes.append(f"file count truncated at {_FILE_COUNT_LIMIT}")

    blocked_path_hits: list[str] = []
    if is_directory:
        for entry in blocked_paths:
            name = (entry or "").strip()
            if not name:
                continue
            stripped = name.rstrip("/")
            if not stripped or any(part in ("..", "") for part in Path(stripped).parts):
                continue
            target = path / stripped
            if target.exists():
                blocked_path_hits.append(name)

    return {
        "exists": exists,
        "is_directory": is_directory,
        "is_git_repo": is_git_repo,
        "current_branch": None,
        "dirty": False,
        "file_count_estimate": file_count_estimate,
        "blocked_path_hits": blocked_path_hits,
        "notes": notes,
    }


def _bounded_count(path: Path) -> int:
    count = 0
    stack: list[Path] = [path]
    while stack and count < _FILE_COUNT_LIMIT:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if count >= _FILE_COUNT_LIMIT:
                        break
                    if entry.name == ".git":
                        continue
                    count += 1
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except OSError:
                        continue
        except (PermissionError, FileNotFoundError, NotADirectoryError):
            continue
    return count
