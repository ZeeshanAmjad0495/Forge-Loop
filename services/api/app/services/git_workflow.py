"""Task 37: Local Git Branch Workflow service.

A narrow, allow-listed git boundary for workspace-scoped operations. Every
public method composes a small, fixed argv list and routes it through a single
``_run_git`` helper that enforces:

- ``subprocess.run(shell=False, env={"PATH": …})``
- ``cwd`` = workspace root only
- timeout cap + output cap
- an argv top-level allow-list (defense in depth against future regressions)

There is no generic "run any git command" entrypoint. Forbidden operations
(pull, fetch, merge, rebase, reset, clean, remote, config, stash, tag,
worktree, cherry-pick, checkout-anything) are never constructed and would
be rejected by the allow-list even if they were.

Task 38 narrowly allows ``push`` for the GitHub PR publication flow.
``push`` is the only relaxation. The push helper still rejects unsafe
branch names, refuses ``--force``/``--mirror``/``--tags``/refspec/upstream
flags, redacts the token before audit, and is itself gated by
``GITHUB_PUSH_ENABLED``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from .. import config as _config
from ..models import (
    Approval,
    Artifact,
    GitCommitCreate,
    GitCommitRecord,
    GitInspectionResponse,
    WorkspaceBranch,
    WorkspaceBranchCreate,
    WorkspaceBranchResponse,
)


TRUNCATION_MARKER = "\n...[truncated]"

# Allow-listed top-level git command tokens. ``-c`` is allowed as a prefix for
# the commit-identity case; ``_run_git`` recognizes it specially.
_ALLOWED_TOP_LEVEL: frozenset[str] = frozenset({
    "rev-parse",
    "status",
    "diff",
    "switch",
    "add",
    "commit",
    "branch",  # only used with --list/--show-current internally
    "push",  # Task 38: PR publication only; argv shape is enforced separately
})

# Push argv flags that must never appear. Defense in depth — the
# publication path never constructs these.
_PUSH_FORBIDDEN_FLAGS: frozenset[str] = frozenset({
    "--force",
    "-f",
    "--mirror",
    "--tags",
    "--all",
    "--set-upstream",
    "-u",
    "--delete",
    "-d",
    "--force-with-lease",
    "--prune",
})

_REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9._\-/]{1,180}$")

# Forbidden substrings/characters never allowed in any branch name.
_BRANCH_BAD_CHARS = set(" \t\r\n\x00~^:?*[\\")

# Server-side blocklist applied to commit paths in addition to the safety
# profile's blocked_paths.
_BUILTIN_SECRET_PATH_PREFIXES = (
    ".env",
    "secrets/",
    "id_rsa",
    "id_dsa",
    ".aws/",
    ".ssh/",
)


class GitOperationError(RuntimeError):
    """Raised when a git subprocess invocation fails for a non-user reason."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_git_binary() -> str:
    cfg = (getattr(_config, "GIT_BINARY", "") or "").strip()
    return cfg or "git"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _truncate(text: str, cap: int) -> str:
    if cap <= 0:
        return ""
    if len(text) <= cap:
        return text
    head = text[: max(0, cap - len(TRUNCATION_MARKER))]
    return head + TRUNCATION_MARKER


def _redact_token(text: str, token: str | None) -> str:
    """Replace a token value (and its URL-embedded form) with ``***``.

    No-op when ``token`` is None/empty. Also redacts the
    ``x-access-token:<TOKEN>@`` form used when push URLs embed credentials.
    """
    if not token or not text:
        return text or ""
    out = text.replace(token, "***")
    # Common HTTP basic-auth-style embedding in git remote URLs.
    out = out.replace(f"x-access-token:{token}", "x-access-token:***")
    out = out.replace(f":{token}@", ":***@")
    return out


def _expose_redact_token():
    """Module-level alias kept for tests that import the helper directly."""
    return _redact_token


def _validate_branch_name(name: str, *, prefix: str, protected: set[str]) -> None:
    if not name:
        raise HTTPException(status_code=400, detail="branch name is empty")
    if "\x00" in name or any(c in _BRANCH_BAD_CHARS for c in name):
        raise HTTPException(status_code=400, detail="branch name contains unsafe characters")
    if ".." in name or "@{" in name:
        raise HTTPException(status_code=400, detail="branch name contains forbidden sequence")
    if name.startswith("-"):
        raise HTTPException(status_code=400, detail="branch name must not start with '-'")
    if name.endswith("/") or name.endswith(".lock") or name.endswith("."):
        raise HTTPException(status_code=400, detail="branch name has invalid suffix")
    if not _BRANCH_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="branch name has invalid characters")
    if prefix and not name.startswith(prefix):
        raise HTTPException(
            status_code=400,
            detail=f"branch name must start with '{prefix}'",
        )
    short = name.split("/")[0]
    lowered = name.lower()
    for p in protected:
        p_lower = p.strip().lower()
        if not p_lower:
            continue
        if lowered == p_lower or short.lower() == p_lower or lowered.startswith(p_lower + "/"):
            raise HTTPException(
                status_code=400,
                detail=f"branch name conflicts with protected branch '{p}'",
            )


def _validate_base_branch_token(base: str) -> None:
    if not base:
        raise HTTPException(status_code=400, detail="base_branch is empty")
    if any(c in _BRANCH_BAD_CHARS for c in base):
        raise HTTPException(status_code=400, detail="base_branch contains unsafe characters")
    if ".." in base or base.startswith("-") or "\x00" in base:
        raise HTTPException(status_code=400, detail="base_branch is unsafe")
    if not re.match(r"^[A-Za-z0-9._\-/]{1,180}$", base):
        raise HTTPException(status_code=400, detail="base_branch has invalid characters")


def _validate_commit_message(message: str, *, max_len: int) -> str:
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="commit message is empty")
    if "\x00" in message:
        raise HTTPException(status_code=400, detail="commit message contains NUL")
    if len(message) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"commit message exceeds {max_len} characters",
        )
    cleaned = "".join(
        c for c in message if c == "\n" or c == "\t" or 0x20 <= ord(c) < 0x7F or ord(c) >= 0xA0
    )
    if cleaned.startswith("-"):
        raise HTTPException(status_code=400, detail="commit message must not start with '-'")
    return cleaned


def _is_safe_commit_path(rel: str, *, blocked_prefixes: list[str]) -> bool:
    if not rel or rel.startswith("/") or "\x00" in rel:
        return False
    if ".." in rel.split("/"):
        return False
    if any(c in rel for c in "\x00\r\n"):
        return False
    if rel.startswith(".git/") or rel == ".git" or rel.startswith(".forgeloop/"):
        return False

    # Hard-coded secret heuristics that apply to *any* repo.
    basename = rel.rsplit("/", 1)[-1]
    if basename.startswith(".env"):
        return False
    if basename in ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"):
        return False
    if basename.endswith(".pem") or basename.endswith(".key") or basename.endswith(".p12"):
        return False
    if rel.startswith(".aws/") or rel == ".aws":
        return False
    if rel.startswith(".ssh/") or rel == ".ssh":
        return False
    if rel.startswith("secrets/") or rel == "secrets":
        return False

    # Safety-profile blocked_paths (operator-supplied).
    for prefix in blocked_prefixes:
        p = (prefix or "").strip().rstrip("/")
        if not p:
            continue
        if rel == p or rel.startswith(p + "/"):
            return False
    return True


# Status code parser for ``git status --porcelain=v1``. Returns (changed, untracked).
def _parse_porcelain(output: str) -> tuple[list[str], list[str]]:
    changed: list[str] = []
    untracked: list[str] = []
    for line in output.splitlines():
        if not line or len(line) < 3:
            continue
        code = line[:2]
        rest = line[3:]
        if code == "??":
            untracked.append(rest)
            continue
        # Rename "R  old -> new" — keep the new path.
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        changed.append(rest)
    return changed, untracked


# ---------------------------------------------------------------------------
# Subprocess boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _GitResult:
    exit_code: int
    stdout: str
    stderr: str


def _check_top_level(args: list[str]) -> None:
    """Reject argvs whose top-level git command is not in the allow-list.

    The commit identity case uses leading ``-c`` flags (e.g. ``-c user.name=…
    -c user.email=… commit``); we tolerate any leading ``-c key=value`` pair
    so long as the first non-``-c`` token is in ``_ALLOWED_TOP_LEVEL``.
    """
    i = 0
    n = len(args)
    while i < n and args[i] == "-c":
        if i + 1 >= n or "=" not in args[i + 1]:
            raise GitOperationError("malformed -c usage in git argv")
        i += 2
    if i >= n:
        raise GitOperationError("git argv has no top-level command")
    top = args[i]
    if top not in _ALLOWED_TOP_LEVEL:
        raise GitOperationError(f"git top-level command '{top}' is not allowed")


def _run_git(
    *,
    cwd: Path,
    args: list[str],
    timeout: int,
    output_cap: int,
) -> _GitResult:
    _check_top_level(args)
    binary = _resolve_git_binary()
    argv = [binary, *args]
    env = {"PATH": os.environ.get("PATH", "")}
    per_stream = max(0, output_cap // 2)
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (
            exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        )
        stderr = exc.stderr if isinstance(exc.stderr, str) else (
            exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        )
        return _GitResult(
            exit_code=124,
            stdout=_truncate(stdout or "", per_stream),
            stderr=_truncate((stderr or "") + f"\n[timed out after {timeout}s]", per_stream),
        )
    except (FileNotFoundError, OSError) as exc:
        raise GitOperationError(f"git not installed or not on PATH: {exc}") from exc
    return _GitResult(
        exit_code=int(result.returncode),
        stdout=_truncate(result.stdout or "", per_stream),
        stderr=_truncate(result.stderr or "", per_stream),
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _generate_branch_name(
    *,
    dev_task_id: str | None,
    subtask_id: str | None,
    prefix: str,
) -> str:
    p = prefix or "forgeloop/"
    if not p.endswith("/"):
        p = p + "/"
    if dev_task_id:
        return f"{p}dev-task/{dev_task_id}"
    if subtask_id:
        return f"{p}subtask/{subtask_id}"
    return f"{p}manual/{uuid.uuid4().hex[:8]}"


def _resolve_approval(
    *,
    approval_repo,
    approval_id: str | None,
    project_id: str,
    dev_task_id: str | None,
    subtask_id: str | None,
    agent_run_id: str | None,
) -> Approval:
    if approval_id is not None:
        appr = approval_repo.get(approval_id)
        if appr is None:
            raise HTTPException(status_code=400, detail="approval_id not found")
        if appr.status != "approved":
            raise HTTPException(status_code=400, detail="approval is not approved")
        if appr.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="approval does not belong to this project",
            )
        matches = False
        if appr.target_type == "dev_task" and dev_task_id and appr.target_id == dev_task_id:
            matches = True
        elif appr.target_type == "subtask" and subtask_id and appr.target_id == subtask_id:
            matches = True
        elif (
            appr.target_type == "task_decomposition"
            and agent_run_id
            and appr.target_id == agent_run_id
        ):
            matches = True
        if not matches:
            raise HTTPException(
                status_code=400,
                detail="approval does not match this branch's dev_task/subtask",
            )
        return appr

    candidates: list[Approval | None] = []
    if dev_task_id:
        candidates.append(approval_repo.find_approved_for_target("dev_task", dev_task_id))
    if subtask_id:
        candidates.append(approval_repo.find_approved_for_target("subtask", subtask_id))
    if agent_run_id:
        candidates.append(
            approval_repo.find_approved_for_target("task_decomposition", agent_run_id)
        )
    for c in candidates:
        if c is not None:
            return c
    raise HTTPException(
        status_code=400,
        detail="approval required for local git commit",
    )


@dataclass
class GitWorkflowService:
    workspace_repo: object
    dev_task_repo: object
    subtask_repo: object
    project_repo: object
    workspace_branch_repo: object
    git_commit_record_repo: object
    approval_repo: object
    artifact_repo: object
    audit_writer: object
    repo_safety_profile_repo: object
    code_repo_repo: object

    # --- shared loaders ---------------------------------------------------

    def _require_workspace(self, workspace_id: str):
        ws = self.workspace_repo.get(workspace_id)
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws

    def _require_workspace_ready_git(self, workspace) -> Path:
        if workspace.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Workspace is not ready (status={workspace.status})",
            )
        root = Path(workspace.root_path).resolve()
        if not (root / ".git").is_dir():
            raise HTTPException(
                status_code=400,
                detail="workspace is not a git repository",
            )
        return root

    def _protected_set(self, workspace) -> set[str]:
        out: set[str] = set(getattr(_config, "GIT_PROTECTED_BRANCHES", []) or [])
        if workspace.code_repository_id:
            profile = self.repo_safety_profile_repo.get_by_repo(workspace.code_repository_id)
            if profile is not None:
                for b in profile.protected_branches or []:
                    if b:
                        out.add(b)
        return out

    def _blocked_path_prefixes(self, workspace) -> list[str]:
        if not workspace.code_repository_id:
            return []
        profile = self.repo_safety_profile_repo.get_by_repo(workspace.code_repository_id)
        if profile is None:
            return []
        return [p for p in (profile.blocked_paths or []) if p]

    # --- public methods ---------------------------------------------------

    def inspect(self, workspace_id: str, actor_email: str) -> GitInspectionResponse:
        workspace = self._require_workspace(workspace_id)
        flags = {
            "git_workflow_enabled": bool(_config.GIT_WORKFLOW_ENABLED),
            "git_commit_enabled": bool(_config.GIT_COMMIT_ENABLED),
        }
        root = Path(workspace.root_path).resolve()
        is_repo = (root / ".git").is_dir()
        if not is_repo:
            response = GitInspectionResponse(
                workspace_id=workspace.id,
                is_git_repo=False,
                notes=["workspace is not a git repository"],
                **flags,
            )
            self.audit_writer.write(
                "git_inspection_completed",
                "workspace",
                workspace.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={"is_git_repo": False},
            )
            return response

        timeout = int(_config.GIT_TIMEOUT_SECONDS)
        cap = int(_config.GIT_MAX_DIFF_BYTES)

        try:
            branch_res = _run_git(
                cwd=root,
                args=["rev-parse", "--abbrev-ref", "HEAD"],
                timeout=timeout,
                output_cap=cap,
            )
        except GitOperationError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        current_branch = branch_res.stdout.strip() if branch_res.exit_code == 0 else None
        if current_branch == "HEAD":
            current_branch = None  # detached HEAD

        status_res = _run_git(
            cwd=root,
            args=["status", "--porcelain=v1", "--untracked-files=all"],
            timeout=timeout,
            output_cap=cap,
        )
        changed_files: list[str] = []
        untracked_files: list[str] = []
        if status_res.exit_code == 0:
            changed_files, untracked_files = _parse_porcelain(status_res.stdout)

        diff_stat_res = _run_git(
            cwd=root,
            args=["diff", "--stat", "HEAD"],
            timeout=timeout,
            output_cap=cap,
        )
        diff_stat = diff_stat_res.stdout if diff_stat_res.exit_code == 0 else ""

        response = GitInspectionResponse(
            workspace_id=workspace.id,
            is_git_repo=True,
            current_branch=current_branch,
            base_branch=current_branch,
            dirty=bool(changed_files or untracked_files),
            changed_files=changed_files,
            untracked_files=untracked_files,
            diff_stat=_truncate(diff_stat, cap),
            ahead_behind=None,
            notes=[],
            **flags,
        )

        # Persist a small inspection artifact for audit evidence.
        now = _now()
        payload = json.dumps({
            "workspace_id": workspace.id,
            "is_git_repo": True,
            "current_branch": current_branch,
            "changed_files": changed_files,
            "untracked_files": untracked_files,
            "diff_stat": response.diff_stat,
        }, sort_keys=True)
        artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="git_inspection_summary",
            content=payload,
            created_at=now,
        ))

        self.audit_writer.write(
            "git_inspection_completed",
            "workspace",
            workspace.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "is_git_repo": True,
                "current_branch": current_branch,
                "dirty": response.dirty,
                "changed_files_count": len(changed_files),
                "untracked_files_count": len(untracked_files),
                "artifact_id": artifact_id,
            },
        )
        return response

    def create_branch(
        self,
        workspace_id: str,
        body: WorkspaceBranchCreate,
        actor_email: str,
    ) -> WorkspaceBranchResponse:
        workspace = self._require_workspace(workspace_id)
        if not _config.GIT_WORKFLOW_ENABLED:
            raise HTTPException(status_code=409, detail="GIT_WORKFLOW_DISABLED")

        root = self._require_workspace_ready_git(workspace)
        timeout = int(_config.GIT_TIMEOUT_SECONDS)
        cap = int(_config.GIT_MAX_DIFF_BYTES)

        # Validate linked task/subtask project matches.
        dev_task = None
        if body.dev_task_id:
            dev_task = self.dev_task_repo.get(body.dev_task_id)
            if dev_task is None:
                raise HTTPException(status_code=404, detail="DevTask not found")
            if dev_task.project_id != workspace.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="dev_task does not belong to workspace project",
                )
        subtask = None
        if body.subtask_id:
            subtask = self.subtask_repo.get(body.subtask_id)
            if subtask is None:
                raise HTTPException(status_code=404, detail="Subtask not found")
            if subtask.project_id != workspace.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="subtask does not belong to workspace project",
                )

        # Resolve / validate name.
        prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
        protected = self._protected_set(workspace)
        name = (body.name or "").strip() or _generate_branch_name(
            dev_task_id=body.dev_task_id,
            subtask_id=body.subtask_id,
            prefix=prefix,
        )
        _validate_branch_name(name, prefix=prefix, protected=protected)

        # Verify base branch (if explicit).
        base_branch = (body.base_branch or "").strip() or None
        if base_branch:
            _validate_base_branch_token(base_branch)
            verify = _run_git(
                cwd=root,
                args=["rev-parse", "--verify", "--quiet", f"refs/heads/{base_branch}"],
                timeout=timeout,
                output_cap=cap,
            )
            if verify.exit_code != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"base_branch '{base_branch}' does not exist locally",
                )
        else:
            head_res = _run_git(
                cwd=root,
                args=["rev-parse", "--abbrev-ref", "HEAD"],
                timeout=timeout,
                output_cap=cap,
            )
            if head_res.exit_code == 0:
                hb = head_res.stdout.strip()
                if hb and hb != "HEAD":
                    base_branch = hb

        # Optional approval gate (not required by default for branch creation).
        if body.approval_id:
            agent_run_id = getattr(dev_task, "agent_run_id", None) if dev_task else None
            _resolve_approval(
                approval_repo=self.approval_repo,
                approval_id=body.approval_id,
                project_id=workspace.project_id,
                dev_task_id=body.dev_task_id,
                subtask_id=body.subtask_id,
                agent_run_id=agent_run_id,
            )

        # Persist prepared record.
        now = _now()
        branch_id = str(uuid.uuid4())
        record = WorkspaceBranch(
            id=branch_id,
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            code_repository_id=workspace.code_repository_id,
            dev_task_id=body.dev_task_id,
            subtask_id=body.subtask_id,
            tool_run_id=body.tool_run_id,
            name=name,
            base_branch=base_branch,
            current_branch=None,
            status="prepared",
            created_at=now,
            updated_at=now,
            last_inspected_at=None,
            error_message=None,
        )
        self.workspace_branch_repo.save(record)

        # B17 guard: refuse to start a new branch on top of a dirty working
        # tree. Without this, uncommitted state from a prior dev_task run
        # silently flows into the new branch's first commit (workspace
        # state bleed). Surface it instead so the caller resolves explicitly.
        porcelain = _run_git(
            cwd=root,
            args=["status", "--porcelain=v1"],
            timeout=timeout,
            output_cap=cap,
        )
        if porcelain.exit_code == 0 and porcelain.stdout.strip():
            changed, untracked = _parse_porcelain(porcelain.stdout)
            self.workspace_branch_repo.update(record.model_copy(update={
                "status": "failed",
                "updated_at": _now(),
                "error_message": (
                    "workspace has uncommitted changes; refuse to create branch "
                    "to avoid state bleed (B17)"
                ),
            }))
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "WORKSPACE_DIRTY",
                    "message": (
                        "Workspace has uncommitted changes; refusing to create "
                        "a new branch on top of unrelated state. Resolve "
                        "first (commit / stash / reset)."
                    ),
                    "changed_files": changed[:50],
                    "untracked_files": untracked[:50],
                },
            )

        # Switch -c. Pass base_branch as the start-point so the new branch
        # always starts at the named base, not at whatever HEAD happens to
        # be. Without the explicit start-point, `git switch -c name` uses
        # the current HEAD, which is the original B17 trigger.
        switch_args = ["switch", "-c", name]
        if base_branch:
            switch_args.append(base_branch)
        result = _run_git(
            cwd=root,
            args=switch_args,
            timeout=timeout,
            output_cap=cap,
        )

        completed_at = _now()
        if result.exit_code == 0:
            record = record.model_copy(update={
                "status": "clean",
                "current_branch": name,
                "updated_at": completed_at,
                "last_inspected_at": completed_at,
                "error_message": None,
            })
            self.workspace_branch_repo.update(record)
            self.audit_writer.write(
                "workspace_branch_created",
                "workspace_branch",
                record.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={
                    "workspace_id": workspace.id,
                    "name": name,
                    "base_branch": base_branch,
                    "dev_task_id": body.dev_task_id,
                    "subtask_id": body.subtask_id,
                },
            )
            inspection = self.inspect(workspace.id, actor_email)
            return WorkspaceBranchResponse(workspace_branch=record, inspection=inspection)

        # Failure path.
        stderr = result.stderr.strip()
        record = record.model_copy(update={
            "status": "failed",
            "updated_at": completed_at,
            "error_message": stderr or f"git switch -c exited {result.exit_code}",
        })
        self.workspace_branch_repo.update(record)
        self.audit_writer.write(
            "git_operation_blocked",
            "workspace_branch",
            record.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "name": name,
                "exit_code": result.exit_code,
                "stderr_tail": stderr[-500:],
            },
        )
        raise HTTPException(
            status_code=400,
            detail=f"git switch -c failed: {stderr or 'unknown error'}",
        )

    def list_branches(self, workspace_id: str, actor_email: str) -> list[WorkspaceBranch]:
        self._require_workspace(workspace_id)
        return self.workspace_branch_repo.list_by_workspace(workspace_id)

    def get_branch(self, branch_id: str, actor_email: str) -> WorkspaceBranchResponse:
        record = self.workspace_branch_repo.get(branch_id)
        if record is None:
            raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
        inspection = self.inspect(record.workspace_id, actor_email)
        return WorkspaceBranchResponse(workspace_branch=record, inspection=inspection)

    def inspect_branch(self, branch_id: str, actor_email: str) -> WorkspaceBranchResponse:
        record = self.workspace_branch_repo.get(branch_id)
        if record is None:
            raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
        inspection = self.inspect(record.workspace_id, actor_email)
        now = _now()
        new_status = record.status
        if record.status not in ("failed", "archived", "committed") and inspection.is_git_repo:
            new_status = "dirty" if inspection.dirty else "clean"
        updated = record.model_copy(update={
            "status": new_status,
            "current_branch": inspection.current_branch,
            "last_inspected_at": now,
            "updated_at": now,
        })
        self.workspace_branch_repo.update(updated)
        self.audit_writer.write(
            "workspace_branch_inspected",
            "workspace_branch",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={"workspace_id": updated.workspace_id, "status": new_status},
        )
        return WorkspaceBranchResponse(workspace_branch=updated, inspection=inspection)

    def commit(
        self,
        branch_id: str,
        body: GitCommitCreate,
        actor_email: str,
    ) -> GitCommitRecord:
        record = self.workspace_branch_repo.get(branch_id)
        if record is None:
            raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
        if record.status == "failed":
            raise HTTPException(status_code=400, detail="branch is in failed state")
        if not _config.GIT_COMMIT_ENABLED:
            raise HTTPException(status_code=409, detail="GIT_COMMIT_DISABLED")

        workspace = self._require_workspace(record.workspace_id)
        root = self._require_workspace_ready_git(workspace)
        timeout = int(_config.GIT_TIMEOUT_SECONDS)
        cap = int(_config.GIT_MAX_DIFF_BYTES)
        msg_cap = int(_config.GIT_COMMIT_MESSAGE_MAX_LEN)

        message = _validate_commit_message(body.message, max_len=msg_cap)

        # Approval gate (always required for commits).
        dev_task = None
        if record.dev_task_id:
            dev_task = self.dev_task_repo.get(record.dev_task_id)
        agent_run_id = getattr(dev_task, "agent_run_id", None) if dev_task else None
        _resolve_approval(
            approval_repo=self.approval_repo,
            approval_id=body.approval_id,
            project_id=workspace.project_id,
            dev_task_id=record.dev_task_id,
            subtask_id=record.subtask_id,
            agent_run_id=agent_run_id,
        )

        # Ensure HEAD matches the branch name. Allow one safe switch.
        head_res = _run_git(
            cwd=root,
            args=["rev-parse", "--abbrev-ref", "HEAD"],
            timeout=timeout,
            output_cap=cap,
        )
        current = head_res.stdout.strip() if head_res.exit_code == 0 else ""
        if current != record.name:
            prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
            protected = self._protected_set(workspace)
            _validate_branch_name(record.name, prefix=prefix, protected=protected)
            verify = _run_git(
                cwd=root,
                args=["rev-parse", "--verify", "--quiet", f"refs/heads/{record.name}"],
                timeout=timeout,
                output_cap=cap,
            )
            if verify.exit_code != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"branch '{record.name}' is not present locally",
                )
            sw = _run_git(
                cwd=root,
                args=["switch", record.name],
                timeout=timeout,
                output_cap=cap,
            )
            if sw.exit_code != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"failed to switch to branch: {sw.stderr.strip()}",
                )

        # Build the safe diff set from porcelain status.
        status_res = _run_git(
            cwd=root,
            args=["status", "--porcelain=v1", "--untracked-files=all"],
            timeout=timeout,
            output_cap=cap,
        )
        if status_res.exit_code != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git status failed: {status_res.stderr.strip()}",
            )
        changed, untracked = _parse_porcelain(status_res.stdout)
        all_paths = list(changed) + list(untracked)
        blocked_prefixes = self._blocked_path_prefixes(workspace)
        safe_set = [p for p in all_paths if _is_safe_commit_path(p, blocked_prefixes=blocked_prefixes)]

        # Resolve include_paths intersection.
        if body.include_paths is not None:
            requested = [p.strip() for p in body.include_paths if p and p.strip()]
            invalid = [p for p in requested if not _is_safe_commit_path(p, blocked_prefixes=blocked_prefixes)]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"include_paths contain unsafe entries: {invalid}",
                )
            missing = [p for p in requested if p not in all_paths]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"include_paths not in current diff: {missing}",
                )
            paths_to_add = requested
        else:
            paths_to_add = safe_set

        if not paths_to_add:
            raise HTTPException(
                status_code=400,
                detail="no safe changed paths to commit",
            )

        now = _now()
        commit_id = str(uuid.uuid4())
        prepared = GitCommitRecord(
            id=commit_id,
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            workspace_branch_id=record.id,
            commit_sha=None,
            message=message,
            status="prepared",
            changed_files=list(paths_to_add),
            diff_stat="",
            artifact_id=None,
            created_at=now,
            updated_at=now,
            error_message=None,
        )
        self.git_commit_record_repo.save(prepared)
        self.audit_writer.write(
            "workspace_commit_prepared",
            "git_commit_record",
            prepared.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "workspace_branch_id": record.id,
                "paths_count": len(paths_to_add),
            },
        )

        # git add -- <paths>
        add_res = _run_git(
            cwd=root,
            args=["add", "--", *paths_to_add],
            timeout=timeout,
            output_cap=cap,
        )
        if add_res.exit_code != 0:
            failed = prepared.model_copy(update={
                "status": "failed",
                "updated_at": _now(),
                "error_message": f"git add failed: {add_res.stderr.strip()}",
            })
            self.git_commit_record_repo.update(failed)
            self.audit_writer.write(
                "workspace_commit_failed",
                "git_commit_record",
                failed.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={"stderr_tail": add_res.stderr[-500:]},
            )
            raise HTTPException(
                status_code=400,
                detail=f"git add failed: {add_res.stderr.strip()}",
            )

        commit_res = _run_git(
            cwd=root,
            args=[
                "-c", "user.name=ForgeLoop",
                "-c", "user.email=forgeloop@local",
                "commit",
                "-m", message,
                "--no-gpg-sign",
            ],
            timeout=timeout,
            output_cap=cap,
        )
        if commit_res.exit_code != 0:
            failed = prepared.model_copy(update={
                "status": "failed",
                "updated_at": _now(),
                "error_message": f"git commit failed: {commit_res.stderr.strip() or commit_res.stdout.strip()}",
            })
            self.git_commit_record_repo.update(failed)
            self.audit_writer.write(
                "workspace_commit_failed",
                "git_commit_record",
                failed.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={
                    "stderr_tail": commit_res.stderr[-500:],
                    "exit_code": commit_res.exit_code,
                },
            )
            raise HTTPException(
                status_code=400,
                detail=f"git commit failed: {commit_res.stderr.strip() or 'unknown error'}",
            )

        sha_res = _run_git(
            cwd=root,
            args=["rev-parse", "HEAD"],
            timeout=timeout,
            output_cap=cap,
        )
        commit_sha = sha_res.stdout.strip() if sha_res.exit_code == 0 else None

        stat_res = _run_git(
            cwd=root,
            args=["diff", "--stat", "HEAD~1..HEAD"],
            timeout=timeout,
            output_cap=cap,
        )
        diff_stat = stat_res.stdout if stat_res.exit_code == 0 else ""

        completed_at = _now()
        artifact_payload = json.dumps({
            "workspace_id": workspace.id,
            "workspace_branch_id": record.id,
            "commit_sha": commit_sha,
            "changed_files": list(paths_to_add),
            "diff_stat": _truncate(diff_stat, cap),
            "message": message,
        }, sort_keys=True)
        artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="git_commit_summary",
            content=artifact_payload,
            created_at=completed_at,
        ))

        committed = prepared.model_copy(update={
            "status": "committed",
            "commit_sha": commit_sha,
            "diff_stat": _truncate(diff_stat, cap),
            "artifact_id": artifact_id,
            "updated_at": completed_at,
            "error_message": None,
        })
        self.git_commit_record_repo.update(committed)

        # Bump parent branch to "committed".
        self.workspace_branch_repo.update(record.model_copy(update={
            "status": "committed",
            "updated_at": completed_at,
            "last_inspected_at": completed_at,
        }))

        self.audit_writer.write(
            "workspace_commit_created",
            "git_commit_record",
            committed.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "workspace_branch_id": record.id,
                "commit_sha": commit_sha,
                "paths_count": len(paths_to_add),
            },
        )
        return committed

    def list_commits(self, branch_id: str, actor_email: str) -> list[GitCommitRecord]:
        record = self.workspace_branch_repo.get(branch_id)
        if record is None:
            raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
        return self.git_commit_record_repo.list_by_branch(branch_id)

    # --- Task 38: narrow push helper -------------------------------------

    def push_forgeloop_branch(
        self,
        *,
        workspace,
        branch_name: str,
        remote_name: str = "origin",
        remote_url_with_token: str | None = None,
        token: str | None = None,
    ) -> tuple["_GitResult", str]:
        """Push a single ForgeLoop-scoped branch to a single remote.

        Returns ``(result, sanitized_remote_label)`` where the label is the
        plain remote name (never the auth URL). All stdout/stderr is
        token-redacted on return.
        """
        if not _config.GITHUB_PUSH_ENABLED:
            raise HTTPException(status_code=409, detail="GITHUB_PUSH_DISABLED")

        root = self._require_workspace_ready_git(workspace)
        timeout = int(_config.GIT_TIMEOUT_SECONDS)
        cap = int(_config.GIT_MAX_DIFF_BYTES)

        prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
        protected = self._protected_set(workspace)
        _validate_branch_name(branch_name, prefix=prefix, protected=protected)

        if not _REMOTE_NAME_RE.match(remote_name or ""):
            raise HTTPException(status_code=400, detail="invalid remote_name")

        # Confirm local branch exists.
        verify = _run_git(
            cwd=root,
            args=["rev-parse", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            timeout=timeout,
            output_cap=cap,
        )
        if verify.exit_code != 0:
            raise HTTPException(
                status_code=400,
                detail=f"local branch '{branch_name}' not found",
            )

        # Build argv — explicitly minimal. No flags. No refspec.
        push_target = remote_url_with_token if remote_url_with_token else remote_name
        argv = ["push", push_target, branch_name]
        # Defense in depth: scan our own constructed argv.
        for tok in argv:
            if tok in _PUSH_FORBIDDEN_FLAGS:
                raise HTTPException(
                    status_code=400, detail=f"forbidden push flag: {tok}"
                )

        result = _run_git(
            cwd=root,
            args=argv,
            timeout=timeout,
            output_cap=cap,
        )

        # Redact the token from captured output before returning.
        redacted_stdout = _redact_token(result.stdout, token)
        redacted_stderr = _redact_token(result.stderr, token)
        sanitized = _GitResult(
            exit_code=result.exit_code,
            stdout=redacted_stdout,
            stderr=redacted_stderr,
        )
        return sanitized, remote_name


def _service() -> GitWorkflowService:
    from ..repositories_state import (
        approval_repo,
        artifact_repo,
        audit_writer,
        code_repo_repo,
        dev_task_repo,
        git_commit_record_repo,
        project_repo,
        repo_safety_profile_repo,
        subtask_repo,
        workspace_branch_repo,
        workspace_repo,
    )
    return GitWorkflowService(
        workspace_repo=workspace_repo,
        dev_task_repo=dev_task_repo,
        subtask_repo=subtask_repo,
        project_repo=project_repo,
        workspace_branch_repo=workspace_branch_repo,
        git_commit_record_repo=git_commit_record_repo,
        approval_repo=approval_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
        repo_safety_profile_repo=repo_safety_profile_repo,
        code_repo_repo=code_repo_repo,
    )


# Convenience function wrappers used by routes.

def inspect(workspace_id: str, actor_email: str) -> GitInspectionResponse:
    return _service().inspect(workspace_id, actor_email)


def create_branch(
    workspace_id: str, body: WorkspaceBranchCreate, actor_email: str
) -> WorkspaceBranchResponse:
    return _service().create_branch(workspace_id, body, actor_email)


def list_branches(workspace_id: str, actor_email: str) -> list[WorkspaceBranch]:
    return _service().list_branches(workspace_id, actor_email)


def get_branch(branch_id: str, actor_email: str) -> WorkspaceBranchResponse:
    return _service().get_branch(branch_id, actor_email)


def inspect_branch(branch_id: str, actor_email: str) -> WorkspaceBranchResponse:
    return _service().inspect_branch(branch_id, actor_email)


def commit(branch_id: str, body: GitCommitCreate, actor_email: str) -> GitCommitRecord:
    return _service().commit(branch_id, body, actor_email)


def list_commits(branch_id: str, actor_email: str) -> list[GitCommitRecord]:
    return _service().list_commits(branch_id, actor_email)


def git_available() -> bool:
    return shutil.which(_resolve_git_binary()) is not None


__all__ = [
    "GitOperationError",
    "GitWorkflowService",
    "commit",
    "create_branch",
    "get_branch",
    "git_available",
    "inspect",
    "inspect_branch",
    "list_branches",
    "list_commits",
]
