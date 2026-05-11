"""PR review orchestration extracted from the route layer.

Owns the three `pr_review_*` audit events and the multi-repo context
gathering. The Kody adapter is the LLM/adapter boundary and stays in
`pr_review/kody.py`.

Behaviour is byte-identical to the pre-S3 inline handler — same audit
strings, same status transitions, same field ordering.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..models import (
    Artifact,
    AuditAction,
    PullRequestDraft,
    PullRequestReview,
    PullRequestReviewComplete,
    PullRequestReviewCreate,
    PullRequestReviewUpdate,
)
from ..pr_review.kody import (
    KodyReviewAdapter,
    build_kody_review_package,
    is_allowed_review_status_transition,
)
from ..repositories_state import (
    approval_repo,
    artifact_repo,
    audit_writer,
    check_run_repo,
    code_repo_repo,
    dev_task_repo,
    epic_repo,
    pr_draft_repo,
    pr_review_repo,
    project_repo,
    repo_safety_profile_repo,
    requirement_repo,
    subtask_repo,
    tool_run_repo,
)

_kody_review_adapter = KodyReviewAdapter()


def gather_review_context(draft: PullRequestDraft):
    project = project_repo.get(draft.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    code_repository = code_repo_repo.get(draft.code_repository_id)
    if code_repository is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")

    dev_task = dev_task_repo.get(draft.dev_task_id) if draft.dev_task_id else None
    subtask = subtask_repo.get(draft.subtask_id) if draft.subtask_id else None
    tool_run = tool_run_repo.get(draft.tool_run_id) if draft.tool_run_id else None
    safety_profile = repo_safety_profile_repo.get_by_repo(code_repository.id)

    requirement = None
    epic = None
    if dev_task is not None:
        if dev_task.requirement_id:
            requirement = requirement_repo.get(dev_task.requirement_id)
        if dev_task.epic_id:
            epic = epic_repo.get(dev_task.epic_id)

    check_runs: list = []
    if dev_task is not None:
        check_runs = check_run_repo.list_by_target("dev_task", dev_task.id)
    elif subtask is not None:
        check_runs = check_run_repo.list_by_target("subtask", subtask.id)

    approvals: list = []
    if dev_task is not None or subtask is not None:
        target_type = "dev_task" if dev_task is not None else "subtask"
        target_id = dev_task.id if dev_task is not None else subtask.id
        approvals = [
            a for a in approval_repo.list_by_project(draft.project_id)
            if a.target_type == target_type and a.target_id == target_id
        ]

    return (
        project,
        code_repository,
        safety_profile,
        dev_task,
        subtask,
        requirement,
        epic,
        tool_run,
        check_runs,
        approvals,
    )


def create_review(pr_draft_id: str, body: PullRequestReviewCreate, current_user: str) -> PullRequestReview:
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")

    (
        project,
        code_repository,
        safety_profile,
        dev_task,
        subtask,
        requirement,
        epic,
        tool_run,
        check_runs,
        approvals,
    ) = gather_review_context(draft)

    now = datetime.now(timezone.utc)
    is_manual_completed = body.mode == "manual" and body.conclusion is not None

    if is_manual_completed:
        status = "completed"
        conclusion = body.conclusion
        completed_at = now
        started_at = now
        raw_output = body.raw_output
        summary = body.summary or ""
    else:
        package = build_kody_review_package(
            pr_draft=draft,
            project=project,
            code_repository=code_repository,
            safety_profile=safety_profile,
            dev_task=dev_task,
            subtask=subtask,
            requirement=requirement,
            epic=epic,
            tool_run=tool_run,
            check_runs=check_runs,
            approvals=approvals,
        )
        status = "pending"
        conclusion = None
        completed_at = None
        started_at = None
        raw_output = body.raw_output if body.raw_output is not None else json.dumps(package)
        summary = body.summary or ""

    linked_artifact_id: str | None = None
    if raw_output:
        linked_artifact_id = str(uuid.uuid4())
        artifact_repo.save(Artifact(
            id=linked_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="pr_review",
            content=raw_output,
            created_at=now,
        ))
    review = PullRequestReview(
        id=str(uuid.uuid4()),
        project_id=draft.project_id,
        code_repository_id=draft.code_repository_id,
        pr_draft_id=draft.id,
        provider=body.provider,
        status=status,
        conclusion=conclusion,
        summary=summary,
        findings=list(body.findings or []),
        recommendations=body.recommendations,
        raw_output=raw_output,
        artifact_id=linked_artifact_id,
        external_review_url=body.external_review_url,
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
        error_message=None,
    )
    pr_review_repo.save(review)

    action: AuditAction = "pr_review_recorded" if is_manual_completed else "pr_review_requested"
    audit_writer.write(
        action, "pr_review", review.id,
        project_id=draft.project_id, actor_email=current_user,
        details={
            "pr_draft_id": draft.id,
            "review_id": review.id,
            "provider": review.provider,
            "conclusion": review.conclusion,
        },
    )
    return review


def patch_review(review_id: str, body: PullRequestReviewUpdate, current_user: str) -> PullRequestReview:
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return review

    target_status = patch.get("status")
    if target_status is not None:
        if not is_allowed_review_status_transition(review.status, target_status):
            raise HTTPException(
                status_code=400,
                detail=f"Disallowed status transition: {review.status} -> {target_status}",
            )
        if target_status == "completed":
            target_conclusion = patch.get("conclusion", review.conclusion)
            if target_conclusion is None:
                raise HTTPException(
                    status_code=400,
                    detail="conclusion is required when transitioning to status=completed",
                )

    if "findings" in patch and body.findings is not None:
        patch["findings"] = list(body.findings)

    now = datetime.now(timezone.utc)
    update_fields: dict = {**patch, "updated_at": now}
    if target_status == "completed" and review.completed_at is None:
        update_fields["completed_at"] = now
    if target_status == "running" and review.started_at is None:
        update_fields["started_at"] = now

    updated = review.model_copy(update=update_fields)
    pr_review_repo.update(updated)

    material_fields = {"summary", "findings", "conclusion"}
    if material_fields.intersection(patch.keys()):
        audit_writer.write(
            "pr_review_recorded", "pr_review", review.id,
            project_id=review.project_id, actor_email=current_user,
            details={
                "pr_draft_id": review.pr_draft_id,
                "review_id": review.id,
                "changed_fields": list(patch.keys()),
            },
        )
    return updated


def complete_review(review_id: str, body: PullRequestReviewComplete, current_user: str) -> PullRequestReview:
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PullRequestReview not found")
    if review.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="PullRequestReview is already completed",
        )
    if not is_allowed_review_status_transition(review.status, "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"PullRequestReview in status {review.status!r} cannot be completed",
        )

    now = datetime.now(timezone.utc)
    updated = _kody_review_adapter.record_review_result(
        review=review,
        conclusion=body.conclusion,
        summary=body.summary or "",
        findings=list(body.findings or []),
        recommendations=body.recommendations,
        raw_output=body.raw_output,
    )
    if updated.started_at is None:
        updated = updated.model_copy(update={"started_at": now})
    pr_review_repo.update(updated)
    audit_writer.write(
        "pr_review_completed", "pr_review", review.id,
        project_id=review.project_id, actor_email=current_user,
        details={
            "pr_draft_id": review.pr_draft_id,
            "review_id": review.id,
            "conclusion": updated.conclusion,
        },
    )
    return updated
