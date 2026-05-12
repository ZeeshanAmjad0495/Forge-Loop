"""Task 38: controlled GitHub draft PR publication.

End-to-end orchestration:
- validate every link (PR draft → project → code repo → workspace → branch)
- enforce every gate (status, provider, config, optional approval)
- push exactly one ForgeLoop-scoped branch via :mod:`git_workflow`
- POST exactly one draft PR via :mod:`github_client`
- update the PullRequestDraft atomically with external PR metadata
- record audit + artifact evidence (token-redacted everywhere)

Never merges. Never deploys. Never calls GitHub for anything else.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from .. import config as _config
from ..models import (
    Approval,
    Artifact,
    GitHubDraftCreate,
    GitHubDraftCreationResponse,
    GitHubPublicationSummary,
    PullRequestDraft,
)
from . import git_workflow as _git_workflow
from . import github_client as _github_client
from .github_repo import GitHubRepoUrlError, parse_owner_repo


_BASE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._\-/]{1,180}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_target_branch(name: str) -> None:
    if not name:
        raise HTTPException(status_code=400, detail="target_branch is empty")
    if any(c in name for c in " \t\r\n\x00~^:?*[\\"):
        raise HTTPException(status_code=400, detail="target_branch contains unsafe characters")
    if ".." in name or name.startswith("-"):
        raise HTTPException(status_code=400, detail="target_branch is unsafe")
    if not _BASE_BRANCH_RE.match(name):
        raise HTTPException(status_code=400, detail="target_branch has invalid characters")


def _validate_forgeloop_branch(name: str, protected: set[str]) -> None:
    prefix = _config.GIT_ALLOWED_BRANCH_PREFIX or "forgeloop/"
    if not name or not name.startswith(prefix):
        raise HTTPException(
            status_code=400,
            detail=f"branch '{name}' is not ForgeLoop-scoped",
        )
    short = name.split("/")[0].lower()
    lowered = name.lower()
    for p in protected:
        p_lower = (p or "").strip().lower()
        if not p_lower:
            continue
        if lowered == p_lower or short == p_lower or lowered.startswith(p_lower + "/"):
            raise HTTPException(
                status_code=400,
                detail=f"branch '{name}' is protected",
            )


def _resolve_approval(
    *,
    approval_repo,
    approval_id: str | None,
    project_id: str,
    pr_draft_id: str,
    dev_task_id: str | None,
    subtask_id: str | None,
    agent_run_id: str | None,
) -> Approval | None:
    if approval_id is None:
        return None
    appr = approval_repo.get(approval_id)
    if appr is None:
        raise HTTPException(status_code=400, detail="approval_id not found")
    if appr.status != "approved":
        raise HTTPException(status_code=400, detail="approval is not approved")
    if appr.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="approval does not belong to PR draft's project",
        )
    matches = False
    if appr.target_type == "artifact" and appr.target_id == pr_draft_id:
        matches = True
    elif appr.target_type == "dev_task" and dev_task_id and appr.target_id == dev_task_id:
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
            detail="approval does not match this PR draft",
        )
    return appr


@dataclass
class PrPublicationService:
    pr_draft_repo: object
    project_repo: object
    code_repo_repo: object
    workspace_repo: object
    workspace_branch_repo: object
    dev_task_repo: object
    subtask_repo: object
    approval_repo: object
    repo_safety_profile_repo: object
    artifact_repo: object
    audit_writer: object

    # Indirection so tests can fully swap the boundaries.
    def _git_service(self):
        return _git_workflow._service()

    def _github_client(self):
        return _github_client.GITHUB_CLIENT

    def publish_github_draft(
        self,
        pr_draft_id: str,
        body: GitHubDraftCreate,
        actor_email: str,
    ) -> GitHubDraftCreationResponse:
        draft = self.pr_draft_repo.get(pr_draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="PullRequestDraft not found")

        project = self.project_repo.get(draft.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        code_repository = self.code_repo_repo.get(draft.code_repository_id)
        if code_repository is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
        workspace = self.workspace_repo.get(body.workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        branch = self.workspace_branch_repo.get(body.workspace_branch_id)
        if branch is None:
            raise HTTPException(status_code=404, detail="WorkspaceBranch not found")

        # Cross-link validation.
        if code_repository.project_id != project.id:
            raise HTTPException(
                status_code=400,
                detail="CodeRepository does not belong to PR draft's project",
            )
        if workspace.project_id != project.id:
            raise HTTPException(
                status_code=400,
                detail="Workspace does not belong to PR draft's project",
            )
        if branch.project_id != project.id:
            raise HTTPException(
                status_code=400,
                detail="WorkspaceBranch does not belong to PR draft's project",
            )
        if branch.workspace_id != workspace.id:
            raise HTTPException(
                status_code=400,
                detail="WorkspaceBranch does not belong to workspace",
            )

        # Status gate.
        if draft.status != "approved_for_creation":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"PullRequestDraft in status {draft.status!r} is not "
                    "approved_for_creation"
                ),
            )

        # Provider checks.
        if code_repository.provider != "github":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"CodeRepository provider {code_repository.provider!r} "
                    "is not 'github'"
                ),
            )

        # Parse owner/repo from repo_url.
        try:
            owner, repo = parse_owner_repo(code_repository.repo_url)
        except GitHubRepoUrlError as exc:
            self.audit_writer.write(
                "github_pr_creation_blocked",
                "pr_draft",
                draft.id,
                project_id=project.id,
                actor_email=actor_email,
                details={"reason": "unsupported_repo_url"},
            )
            raise HTTPException(status_code=400, detail=str(exc))

        # Branch safety: ForgeLoop-scoped + not protected.
        protected: set[str] = set(_config.GIT_PROTECTED_BRANCHES or [])
        if workspace.code_repository_id:
            profile = self.repo_safety_profile_repo.get_by_repo(workspace.code_repository_id)
            if profile is not None:
                for p in profile.protected_branches or []:
                    if p:
                        protected.add(p)
        _validate_forgeloop_branch(branch.name, protected)
        _validate_target_branch(draft.target_branch)

        # Config gates.
        if not _config.GITHUB_INTEGRATION_ENABLED:
            self.audit_writer.write(
                "github_pr_creation_blocked",
                "pr_draft",
                draft.id,
                project_id=project.id,
                actor_email=actor_email,
                details={"reason": "integration_disabled"},
            )
            raise HTTPException(status_code=409, detail="GITHUB_INTEGRATION_DISABLED")
        from . import secrets as _secrets
        token = (_secrets.get_secret("GITHUB_TOKEN") or _config.GITHUB_TOKEN or "").strip()
        if not token:
            raise HTTPException(status_code=409, detail="GITHUB_TOKEN_NOT_CONFIGURED")

        # Optional approval gate (additive; status is the primary gate).
        dev_task = None
        if draft.dev_task_id:
            dev_task = self.dev_task_repo.get(draft.dev_task_id)
        agent_run_id = getattr(dev_task, "agent_run_id", None) if dev_task else None
        _resolve_approval(
            approval_repo=self.approval_repo,
            approval_id=body.approval_id,
            project_id=project.id,
            pr_draft_id=draft.id,
            dev_task_id=draft.dev_task_id,
            subtask_id=draft.subtask_id,
            agent_run_id=agent_run_id,
        )

        # Record the request.
        self.audit_writer.write(
            "github_pr_creation_requested",
            "pr_draft",
            draft.id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "workspace_id": workspace.id,
                "workspace_branch_id": branch.id,
                "branch": branch.name,
                "target": draft.target_branch,
                "push_branch": bool(body.push_branch),
            },
        )

        # Push step (optional).
        pushed = False
        push_exit_code: int | None = None
        push_stdout_tail = ""
        push_stderr_tail = ""
        remote_label: str | None = None
        if body.push_branch:
            remote_url_with_token = (
                f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
            )
            git_service = self._git_service()
            try:
                push_result, remote_label = git_service.push_forgeloop_branch(
                    workspace=workspace,
                    branch_name=branch.name,
                    remote_name=body.remote_name or _config.GITHUB_DEFAULT_REMOTE,
                    remote_url_with_token=remote_url_with_token,
                    token=token,
                )
            except HTTPException:
                raise
            except Exception as exc:
                self._mark_draft_failed(
                    draft,
                    actor_email,
                    reason="push_error",
                    message=_git_workflow._redact_token(str(exc), token),
                )
                raise HTTPException(
                    status_code=502,
                    detail="git push failed (see audit trail)",
                ) from None

            push_exit_code = push_result.exit_code
            push_stdout_tail = push_result.stdout[-2000:]
            push_stderr_tail = push_result.stderr[-2000:]
            if push_exit_code != 0:
                self._mark_draft_failed(
                    draft,
                    actor_email,
                    reason="push_nonzero",
                    message=_git_workflow._redact_token(
                        push_stderr_tail or f"git push exited {push_exit_code}",
                        token,
                    ),
                    details={
                        "exit_code": push_exit_code,
                        "remote": remote_label,
                    },
                )
                raise HTTPException(
                    status_code=502,
                    detail="git push exited non-zero (see audit trail)",
                )
            pushed = True
            self.audit_writer.write(
                "github_branch_pushed",
                "pr_draft",
                draft.id,
                project_id=project.id,
                actor_email=actor_email,
                details={
                    "remote": remote_label,
                    "branch": branch.name,
                    "exit_code": push_exit_code,
                },
            )

        # PR creation.
        try:
            created = self._github_client().create_draft_pull_request(
                owner=owner,
                repo=repo,
                title=draft.title,
                body=draft.body,
                head=branch.name,
                base=draft.target_branch,
                draft=bool(body.draft),
                token=token,
            )
        except _github_client.GitHubAuthError as exc:
            self._mark_draft_failed(
                draft, actor_email, reason="auth",
                message=_git_workflow._redact_token(str(exc), token),
            )
            raise HTTPException(status_code=502, detail="github_auth_failed") from None
        except _github_client.GitHubNotFoundError as exc:
            self._mark_draft_failed(
                draft, actor_email, reason="not_found",
                message=_git_workflow._redact_token(str(exc), token),
            )
            raise HTTPException(status_code=502, detail="github_not_found") from None
        except _github_client.GitHubValidationError as exc:
            self._mark_draft_failed(
                draft, actor_email, reason="validation",
                message=_git_workflow._redact_token(str(exc), token),
            )
            raise HTTPException(status_code=422, detail="github_validation_failed") from None
        except _github_client.GitHubError as exc:
            self._mark_draft_failed(
                draft, actor_email, reason="github_error",
                message=_git_workflow._redact_token(str(exc), token),
            )
            raise HTTPException(status_code=502, detail="github_error") from None

        # Success — update draft atomically.
        now = _now()
        updated = draft.model_copy(update={
            "status": "created",
            "provider": "github",
            "external_pr_url": created.url,
            "external_pr_number": created.number,
            "source_branch": branch.name,
            "workspace_id": workspace.id,
            "workspace_branch_id": branch.id,
            "github_owner": owner,
            "github_repo": repo,
            "last_published_at": now,
            "updated_at": now,
            "error_message": None,
        })
        self.pr_draft_repo.update(updated)

        # Build summary + artifact.
        summary = GitHubPublicationSummary(
            pushed=pushed,
            remote_name=remote_label,
            pushed_branch=branch.name if pushed else None,
            push_exit_code=push_exit_code,
            github_owner=owner,
            github_repo=repo,
            external_pr_url=created.url,
            external_pr_number=created.number,
            head=created.head,
            base=created.base,
            draft=created.draft,
        )
        artifact_payload = json.dumps({
            "pr_draft_id": draft.id,
            "workspace_id": workspace.id,
            "workspace_branch_id": branch.id,
            "code_repository_id": code_repository.id,
            "owner": owner,
            "repo": repo,
            "head": created.head,
            "base": created.base,
            "draft": created.draft,
            "external_pr_url": created.url,
            "external_pr_number": created.number,
            "state": created.state,
            "push": {
                "performed": pushed,
                "exit_code": push_exit_code,
                "remote_name": remote_label,
                "stdout_tail": _git_workflow._redact_token(push_stdout_tail, token),
                "stderr_tail": _git_workflow._redact_token(push_stderr_tail, token),
            },
        }, sort_keys=True)
        artifact_id = str(uuid.uuid4())
        self.artifact_repo.save(Artifact(
            id=artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="github_pr_creation_summary",
            content=artifact_payload,
            created_at=now,
        ))

        self.audit_writer.write(
            "github_pr_created",
            "pr_draft",
            draft.id,
            project_id=project.id,
            actor_email=actor_email,
            details={
                "owner": owner,
                "repo": repo,
                "external_pr_number": created.number,
                "external_pr_url": created.url,
                "head": created.head,
                "base": created.base,
                "draft": created.draft,
                "artifact_id": artifact_id,
            },
        )

        return GitHubDraftCreationResponse(
            pr_draft=updated,
            publication_summary=summary,
        )

    # ----- helpers ------------------------------------------------------

    def _mark_draft_failed(
        self,
        draft: PullRequestDraft,
        actor_email: str,
        *,
        reason: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        now = _now()
        updated = draft.model_copy(update={
            "status": "failed",
            "error_message": message[:2000],
            "updated_at": now,
            "last_published_at": now,
        })
        self.pr_draft_repo.update(updated)
        event_details: dict = {"reason": reason}
        if details:
            event_details.update(details)
        self.audit_writer.write(
            "github_pr_creation_failed",
            "pr_draft",
            draft.id,
            project_id=draft.project_id,
            actor_email=actor_email,
            details=event_details,
        )


def _service() -> PrPublicationService:
    from ..repositories_state import (
        approval_repo,
        artifact_repo,
        audit_writer,
        code_repo_repo,
        dev_task_repo,
        pr_draft_repo,
        project_repo,
        repo_safety_profile_repo,
        subtask_repo,
        workspace_branch_repo,
        workspace_repo,
    )
    return PrPublicationService(
        pr_draft_repo=pr_draft_repo,
        project_repo=project_repo,
        code_repo_repo=code_repo_repo,
        workspace_repo=workspace_repo,
        workspace_branch_repo=workspace_branch_repo,
        dev_task_repo=dev_task_repo,
        subtask_repo=subtask_repo,
        approval_repo=approval_repo,
        repo_safety_profile_repo=repo_safety_profile_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
    )


def publish_github_draft(
    pr_draft_id: str,
    body: GitHubDraftCreate,
    actor_email: str,
) -> GitHubDraftCreationResponse:
    return _service().publish_github_draft(pr_draft_id, body, actor_email)


__all__ = [
    "PrPublicationService",
    "publish_github_draft",
]
