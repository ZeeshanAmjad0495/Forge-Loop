"""B2: native multi-dev-task integration.

Merges an explicit, ordered list of already-committed ForgeLoop workspace
branches onto a fresh integration branch. Every member's outcome is recorded;
a merge conflict is surfaced as HTTP 409 with the conflicting member and the
conflicting files — it is never silently skipped (the failure mode that
dropped DT-S4-3 during manual hand-merge).

Durable evidence reuses existing repositories: a ``WorkspaceBranch`` for the
integration branch, a ``GitCommitRecord`` for the merge HEAD, an ``Artifact``
summary, audit events, and optionally one ``PullRequestDraft``. No new
collection / no repositories.py change.

Git boundary: a scoped fixed-argv subprocess (``shell=False``, PATH-only env,
timeout). It is deliberately NOT routed through ``git_workflow._run_git``,
whose allow-list intentionally excludes ``merge`` / switch-to-existing —
mirroring the B1 precedent rather than widening that security boundary.

This endpoint never pushes and never targets a protected branch. The eventual
push / PR-to-main still goes through the Task 38 publication gate (approval +
``GITHUB_PUSH_ENABLED``), so local integration is intentionally not
approval-gated here (parity with ``create_branch``).
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from .. import config as _config
from ..models import (
    Artifact,
    GitCommitRecord,
    IntegrationMember,
    IntegrationRunCreate,
    IntegrationRunResult,
    PullRequestDraft,
    WorkspaceBranch,
)
from .git_workflow import (
    _parse_porcelain,
    _resolve_git_binary,
    _truncate,
    _validate_base_branch_token,
    _validate_branch_name,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _git(root: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Scoped, fixed-argv git boundary. No shell, PATH-only env, timeout.

    Deliberately separate from ``git_workflow._run_git`` (B1 precedent):
    merge / switch-to-existing are outside that module's allow-list by design
    and must not be added to it.
    """
    return subprocess.run(
        [_resolve_git_binary(), "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
    )


def _ref_exists(root: Path, name: str, timeout: int) -> bool:
    res = _git(
        root,
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        timeout,
    )
    return res.returncode == 0


def _rev(root: Path, ref: str, timeout: int) -> str | None:
    r = _git(root, ["rev-parse", "--verify", "--quiet", ref], timeout)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _upstream_of(root: Path, base: str, timeout: int) -> str | None:
    """Resolve the base branch's LOCAL upstream/remote-tracking ref.

    No network: only consults refs already present locally. Tries the
    configured upstream first, then the conventional origin/<base>.
    Returns None if no local upstream exists (staleness undeterminable).
    """
    up = _git(
        root,
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{base}@{{upstream}}"],
        timeout,
    )
    if up.returncode == 0 and up.stdout.strip():
        return up.stdout.strip()
    if _rev(root, f"refs/remotes/origin/{base}", timeout):
        return f"origin/{base}"
    return None


def _is_ancestor(root: Path, anc: str, desc: str, timeout: int) -> bool:
    return _git(
        root, ["merge-base", "--is-ancestor", anc, desc], timeout
    ).returncode == 0


@dataclass
class IntegrationRunService:
    workspace_repo: object
    workspace_branch_repo: object
    git_commit_record_repo: object
    artifact_repo: object
    pr_draft_repo: object
    repo_safety_profile_repo: object
    audit_writer: object

    def _protected_set(self, workspace) -> set[str]:
        out: set[str] = set(getattr(_config, "GIT_PROTECTED_BRANCHES", []) or [])
        if workspace.code_repository_id:
            profile = self.repo_safety_profile_repo.get_by_repo(
                workspace.code_repository_id
            )
            if profile is not None:
                for b in profile.protected_branches or []:
                    if b:
                        out.add(b)
        return out

    def create(
        self,
        workspace_id: str,
        body: IntegrationRunCreate,
        *,
        actor_email: str | None,
    ) -> IntegrationRunResult:
        workspace = self.workspace_repo.get(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if not _config.GIT_WORKFLOW_ENABLED:
            raise HTTPException(status_code=409, detail="GIT_WORKFLOW_DISABLED")
        if workspace.status != "ready":
            raise HTTPException(
                status_code=400,
                detail=f"Workspace is not ready (status={workspace.status})",
            )
        root = Path(workspace.root_path).resolve()
        if not (root / ".git").is_dir():
            raise HTTPException(
                status_code=400, detail="workspace is not a git repository"
            )

        ids = list(body.source_branch_ids or [])
        if not ids:
            raise HTTPException(
                status_code=400, detail="source_branch_ids must be non-empty"
            )
        if len(set(ids)) != len(ids):
            raise HTTPException(
                status_code=400, detail="source_branch_ids contains duplicates"
            )

        timeout = int(_config.GIT_TIMEOUT_SECONDS)
        cap = int(_config.GIT_MAX_DIFF_BYTES)
        prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
        protected = self._protected_set(workspace)

        # --- Pre-flight resolution (no git mutation until everything checks
        # out). Any problem rejects the whole run explicitly; nothing is
        # attempted or silently skipped.
        members: list[IntegrationMember] = []
        problems: list[str] = []
        for bid in ids:
            wb = self.workspace_branch_repo.get(bid)
            if wb is None:
                problems.append(f"{bid}: WorkspaceBranch not found")
                continue
            if wb.project_id != workspace.project_id:
                problems.append(f"{bid}: belongs to a different project")
                continue
            if wb.workspace_id != workspace.id:
                problems.append(f"{bid}: belongs to a different workspace")
                continue
            if wb.status not in ("committed", "clean"):
                problems.append(
                    f"{bid}: status {wb.status!r} is not committed/clean"
                )
                continue
            try:
                _validate_branch_name(wb.name, prefix=prefix, protected=protected)
            except HTTPException as exc:
                problems.append(f"{bid}: unsafe branch name ({exc.detail})")
                continue
            members.append(
                IntegrationMember(
                    workspace_branch_id=wb.id,
                    branch_name=wb.name,
                    dev_task_id=wb.dev_task_id,
                    status="pending",
                )
            )
        if problems:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_SOURCE_BRANCHES",
                    "message": "one or more source branches are not integrable",
                    "problems": problems,
                },
            )

        # --- Resolve + verify base branch.
        if body.base_branch:
            _validate_base_branch_token(body.base_branch)
            base_branch = body.base_branch.strip()
        else:
            bases = {
                wb_base
                for wb_base in (
                    self.workspace_branch_repo.get(m.workspace_branch_id).base_branch
                    for m in members
                )
                if wb_base
            }
            if len(bases) == 1:
                base_branch = next(iter(bases))
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "base_branch could not be inferred (members have "
                        f"{len(bases)} distinct bases); specify base_branch"
                    ),
                )
        if not _ref_exists(root, base_branch, timeout):
            raise HTTPException(
                status_code=400,
                detail=f"base_branch '{base_branch}' does not exist locally",
            )

        # --- B2 stale-base detection (local refs only; no fetch). If the
        # base is behind its local upstream (origin/<base>), an integration
        # off it will likely conflict with the *current* base at PR time.
        # Always detect + warn; block only if opted in; reconcile if asked.
        warnings: list[str] = []
        notes: list[str] = []
        base_head = _rev(root, base_branch, timeout)
        base_upstream = _upstream_of(root, base_branch, timeout)
        base_upstream_head = (
            _rev(root, base_upstream, timeout) if base_upstream else None
        )
        base_is_current = True
        if (
            base_upstream
            and base_upstream_head
            and base_head
            and base_head != base_upstream_head
            and _is_ancestor(root, base_branch, base_upstream, timeout)
        ):
            base_is_current = False
            warnings.append(
                f"stale_base: '{base_branch}' is behind '{base_upstream}' "
                f"({base_upstream_head[:10]}); the integration branch / PR "
                "may conflict with the current base"
            )
            self.audit_writer.write(
                "integration_run_requested",
                "workspace",
                workspace.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={
                    "stale_base": True,
                    "base_branch": base_branch,
                    "base_head": base_head,
                    "base_upstream": base_upstream,
                    "base_upstream_head": base_upstream_head,
                },
            )
            if _config.INTEGRATION_REQUIRE_CURRENT_BASE and not body.reconcile_base:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "STALE_BASE",
                        "message": (
                            f"base '{base_branch}' is behind "
                            f"'{base_upstream}'; refuse to integrate onto a "
                            "stale base (set reconcile_base=true or update "
                            "the base)"
                        ),
                        "base_branch": base_branch,
                        "base_head": base_head,
                        "base_upstream": base_upstream,
                        "base_upstream_head": base_upstream_head,
                    },
                )

        # --- Each member branch must exist locally (explicit, pre-mutation).
        missing = [
            m.branch_name
            for m in members
            if not _ref_exists(root, m.branch_name, timeout)
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MISSING_LOCAL_BRANCHES",
                    "message": "source branches are not present locally",
                    "branches": missing,
                },
            )

        # --- Capture original HEAD to restore afterwards (least surprise;
        # mirrors B1's no-bleed philosophy).
        head_res = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout)
        original_branch = (
            head_res.stdout.strip() if head_res.returncode == 0 else ""
        )

        # --- Dirty guard (B17 parity): never integrate on top of unrelated
        # uncommitted state.
        status_res = _git(root, ["status", "--porcelain=v1"], timeout)
        if status_res.returncode == 0 and status_res.stdout.strip():
            changed, untracked = _parse_porcelain(status_res.stdout)
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "WORKSPACE_DIRTY",
                    "message": (
                        "Workspace has uncommitted changes; refusing to start "
                        "an integration run. Resolve first."
                    ),
                    "changed_files": changed[:50],
                    "untracked_files": untracked[:50],
                },
            )

        # --- Integration branch name.
        name = (body.name or "").strip() or f"{prefix}integration/{uuid.uuid4().hex[:8]}"
        _validate_branch_name(name, prefix=prefix, protected=protected)
        if _ref_exists(root, name, timeout):
            raise HTTPException(
                status_code=400,
                detail=f"integration branch '{name}' already exists",
            )

        now = _now()
        record = WorkspaceBranch(
            id=str(uuid.uuid4()),
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            code_repository_id=workspace.code_repository_id,
            dev_task_id=None,
            subtask_id=None,
            tool_run_id=None,
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
        self.audit_writer.write(
            "integration_run_requested",
            "workspace_branch",
            record.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "integration_branch": name,
                "base_branch": base_branch,
                "member_count": len(members),
                "source_branch_ids": ids,
            },
        )

        # --- Create the integration branch off the base.
        sw = _git(root, ["switch", "-c", name, base_branch], timeout)
        if sw.returncode != 0:
            self._fail_record(record, f"git switch -c failed: {sw.stderr.strip()}")
            self.audit_writer.write(
                "integration_run_failed",
                "workspace_branch",
                record.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={"stage": "create_branch", "stderr_tail": sw.stderr[-500:]},
            )
            raise HTTPException(
                status_code=400,
                detail=f"git switch -c failed: {sw.stderr.strip() or 'unknown error'}",
            )

        # --- Sequential merge. First conflict aborts cleanly and surfaces a
        # 409; remaining members are explicitly reported as not_attempted.
        for idx, member in enumerate(members):
            merge = _git(
                root,
                [
                    "-c", "user.name=ForgeLoop",
                    "-c", "user.email=forgeloop@local",
                    "merge", "--no-ff", "--no-edit", "--no-gpg-sign",
                    member.branch_name,
                ],
                timeout,
            )
            if merge.returncode == 0:
                member.status = "merged"
                continue

            # Conflict (or other merge failure) — collect, abort, surface.
            unmerged = _git(
                root, ["diff", "--name-only", "--diff-filter=U"], timeout
            )
            conflict_files = [
                p for p in unmerged.stdout.splitlines() if p.strip()
            ]
            _git(root, ["merge", "--abort"], timeout)
            member.status = "conflict"
            member.conflicting_files = conflict_files
            member.detail = (merge.stderr.strip() or merge.stdout.strip())[-500:]
            for later in members[idx + 1:]:
                later.status = "not_attempted"

            self._fail_record(
                record,
                f"merge conflict on {member.branch_name}: "
                f"{len(conflict_files)} file(s)",
            )
            self._restore_head(root, original_branch, prefix, timeout)
            self.audit_writer.write(
                "integration_run_conflict",
                "workspace_branch",
                record.id,
                project_id=workspace.project_id,
                actor_email=actor_email,
                details={
                    "workspace_id": workspace.id,
                    "integration_branch": name,
                    "conflict_branch": member.branch_name,
                    "conflict_dev_task_id": member.dev_task_id,
                    "conflicting_files": conflict_files[:50],
                    "merged": [
                        m.branch_name for m in members if m.status == "merged"
                    ],
                    "not_attempted": [
                        m.branch_name
                        for m in members
                        if m.status == "not_attempted"
                    ],
                },
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "INTEGRATION_CONFLICT",
                    "message": (
                        f"merge conflict integrating '{member.branch_name}'; "
                        "no member was dropped — see members[]"
                    ),
                    "integration_branch": name,
                    "base_branch": base_branch,
                    "members": [m.model_dump() for m in members],
                    "warnings": warnings,
                },
            )

        # --- B2 reconcile: if the base was stale and the caller asked,
        # merge the current upstream base into the integration branch so
        # the result reflects current base. Conflicts here are surfaced
        # structurally (never silent) just like a member conflict.
        if (not base_is_current) and body.reconcile_base and base_upstream:
            rec = _git(
                root,
                [
                    "-c", "user.name=ForgeLoop",
                    "-c", "user.email=forgeloop@local",
                    "merge", "--no-ff", "--no-edit", "--no-gpg-sign",
                    base_upstream,
                ],
                timeout,
            )
            if rec.returncode != 0:
                unmerged = _git(
                    root, ["diff", "--name-only", "--diff-filter=U"], timeout
                )
                rec_files = [
                    p for p in unmerged.stdout.splitlines() if p.strip()
                ]
                _git(root, ["merge", "--abort"], timeout)
                self._fail_record(
                    record,
                    f"base reconcile conflict vs {base_upstream}: "
                    f"{len(rec_files)} file(s)",
                )
                self._restore_head(root, original_branch, prefix, timeout)
                self.audit_writer.write(
                    "integration_run_conflict",
                    "workspace_branch",
                    record.id,
                    project_id=workspace.project_id,
                    actor_email=actor_email,
                    details={
                        "workspace_id": workspace.id,
                        "integration_branch": name,
                        "stage": "base_reconcile",
                        "base_upstream": base_upstream,
                        "conflicting_files": rec_files[:50],
                    },
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "BASE_RECONCILE_CONFLICT",
                        "message": (
                            "all members merged, but reconciling the current "
                            f"base '{base_upstream}' conflicts — resolve "
                            "before PR (no member was dropped)"
                        ),
                        "integration_branch": name,
                        "base_branch": base_branch,
                        "base_upstream": base_upstream,
                        "conflicting_files": rec_files,
                        "members": [m.model_dump() for m in members],
                    },
                )
            base_is_current = True
            notes.append(
                f"reconciled current base from '{base_upstream}' "
                f"({(base_upstream_head or '')[:10]})"
            )

        # --- All members merged. Record evidence.
        sha_res = _git(root, ["rev-parse", "HEAD"], timeout)
        commit_sha = sha_res.stdout.strip() if sha_res.returncode == 0 else None
        names_res = _git(
            root, ["diff", "--name-only", f"{base_branch}..HEAD"], timeout
        )
        changed_files = [
            p for p in names_res.stdout.splitlines() if p.strip()
        ]
        stat_res = _git(
            root, ["diff", "--stat", f"{base_branch}..HEAD"], timeout
        )
        diff_stat = _truncate(
            stat_res.stdout if stat_res.returncode == 0 else "", cap
        )
        message = (body.pr_title or "").strip() or (
            f"Integrate {len(members)} dev-task branch(es) onto {base_branch}"
        )

        completed = _now()
        commit_record = GitCommitRecord(
            id=str(uuid.uuid4()),
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            workspace_branch_id=record.id,
            commit_sha=commit_sha,
            message=message,
            status="committed",
            changed_files=changed_files,
            diff_stat=diff_stat,
            artifact_id=None,
            created_at=completed,
            updated_at=completed,
            error_message=None,
        )

        artifact_payload = json.dumps(
            {
                "workspace_id": workspace.id,
                "integration_branch": name,
                "base_branch": base_branch,
                "commit_sha": commit_sha,
                "members": [m.model_dump() for m in members],
                "changed_files": changed_files,
                "diff_stat": diff_stat,
            },
            sort_keys=True,
        )
        artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(
            Artifact(
                id=artifact_id,
                ticket_id=None,
                requirement_id=None,
                agent_run_id=None,
                artifact_type="integration_run_summary",
                content=artifact_payload,
                created_at=completed,
            )
        )
        commit_record = commit_record.model_copy(update={"artifact_id": artifact_id})
        self.git_commit_record_repo.save(commit_record)

        record = record.model_copy(
            update={
                "status": "committed",
                "current_branch": name,
                "updated_at": completed,
                "last_inspected_at": completed,
                "error_message": None,
            }
        )
        self.workspace_branch_repo.update(record)

        pr_draft_id: str | None = None
        if body.create_pr_draft:
            code_repository_id = (
                body.code_repository_id or workspace.code_repository_id
            )
            if not code_repository_id:
                notes.append(
                    "pr_draft skipped: no code_repository_id (integration "
                    "branch was still created and recorded)"
                )
            else:
                pr_body = body.pr_body or self._default_pr_body(
                    base_branch, members
                )
                draft = PullRequestDraft(
                    id=str(uuid.uuid4()),
                    project_id=workspace.project_id,
                    code_repository_id=code_repository_id,
                    dev_task_id=None,
                    subtask_id=None,
                    tool_run_id=None,
                    title=message,
                    body=pr_body,
                    source_branch=name,
                    target_branch=body.target_branch,
                    status="draft_prepared",
                    provider="local",
                    created_by=actor_email or "system",
                    created_at=completed,
                    updated_at=completed,
                    workspace_id=workspace.id,
                    workspace_branch_id=record.id,
                )
                self.pr_draft_repo.save(draft)
                pr_draft_id = draft.id

        self._restore_head(root, original_branch, prefix, timeout)

        self.audit_writer.write(
            "integration_run_completed",
            "workspace_branch",
            record.id,
            project_id=workspace.project_id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "integration_branch": name,
                "base_branch": base_branch,
                "commit_sha": commit_sha,
                "merged_branches": [m.branch_name for m in members],
                "git_commit_record_id": commit_record.id,
                "pr_draft_id": pr_draft_id,
                "artifact_id": artifact_id,
            },
        )

        return IntegrationRunResult(
            status="integrated",
            integration_branch=record,
            base_branch=base_branch,
            members=members,
            commit_sha=commit_sha,
            git_commit_record_id=commit_record.id,
            pr_draft_id=pr_draft_id,
            diff_stat=diff_stat,
            notes=notes,
            base_is_current=base_is_current,
            base_head=base_head,
            base_upstream=base_upstream,
            base_upstream_head=base_upstream_head,
            warnings=warnings,
        )

    # --- helpers ---------------------------------------------------------

    def _fail_record(self, record: WorkspaceBranch, message: str) -> None:
        self.workspace_branch_repo.update(
            record.model_copy(
                update={
                    "status": "failed",
                    "updated_at": _now(),
                    "error_message": message,
                }
            )
        )

    def _restore_head(
        self, root: Path, original_branch: str, prefix: str, timeout: int
    ) -> None:
        """Best-effort return to the workspace's pre-integration branch.

        Never raises — the integration outcome is already recorded; failing
        to switch back is a soft note, not a result-changing error.
        """
        if not original_branch or original_branch == "HEAD":
            return
        _git(root, ["switch", original_branch], timeout)

    @staticmethod
    def _default_pr_body(
        base_branch: str, members: list[IntegrationMember]
    ) -> str:
        lines = [
            f"Integration of {len(members)} dev-task branch(es) onto "
            f"`{base_branch}`.",
            "",
            "Integrated branches (in order):",
        ]
        for m in members:
            dt = f" (dev_task {m.dev_task_id})" if m.dev_task_id else ""
            lines.append(f"- `{m.branch_name}`{dt}")
        return "\n".join(lines)


def _service() -> IntegrationRunService:
    from ..repositories_state import (
        artifact_repo,
        audit_writer,
        git_commit_record_repo,
        pr_draft_repo,
        repo_safety_profile_repo,
        workspace_branch_repo,
        workspace_repo,
    )

    return IntegrationRunService(
        workspace_repo=workspace_repo,
        workspace_branch_repo=workspace_branch_repo,
        git_commit_record_repo=git_commit_record_repo,
        artifact_repo=artifact_repo,
        pr_draft_repo=pr_draft_repo,
        repo_safety_profile_repo=repo_safety_profile_repo,
        audit_writer=audit_writer,
    )


def create_integration_run(
    workspace_id: str,
    body: IntegrationRunCreate,
    actor_email: str | None,
) -> IntegrationRunResult:
    return _service().create(workspace_id, body, actor_email=actor_email)


__all__ = [
    "IntegrationRunService",
    "create_integration_run",
]
