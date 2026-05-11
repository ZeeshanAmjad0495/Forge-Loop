import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    PullRequestDraft,
    PullRequestDraftCreate,
    PullRequestDraftUpdate,
)
from ..pr_draft import (
    build_pr_draft_content,
    derive_source_branch,
    is_allowed_status_transition,
)
from ..repositories_state import (
    audit_writer,
    check_run_repo,
    code_repo_repo,
    dev_task_repo,
    epic_repo,
    pr_draft_repo,
    project_repo,
    repo_safety_profile_repo,
    requirement_repo,
    subtask_repo,
    tool_run_repo,
)

router = APIRouter()

_PR_DRAFT_ALLOWED_PROVIDERS = ("manual", "local")


@router.post(
    "/projects/{project_id}/pr-drafts",
    response_model=PullRequestDraft,
    status_code=201,
)
def create_pr_draft(
    project_id: str,
    body: PullRequestDraftCreate,
    current_user: str = Depends(require_auth),
):
    project = project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    repo_obj = code_repo_repo.get(body.code_repository_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    if repo_obj.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail="CodeRepository does not belong to project",
        )

    if body.dev_task_id is None and body.subtask_id is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of dev_task_id or subtask_id is required",
        )

    if body.provider not in _PR_DRAFT_ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"provider={body.provider!r} is not supported in this build. "
                f"Allowed: {list(_PR_DRAFT_ALLOWED_PROVIDERS)}."
            ),
        )

    dev_task = None
    if body.dev_task_id is not None:
        dev_task = dev_task_repo.get(body.dev_task_id)
        if dev_task is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
        if dev_task.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="DevTask does not belong to project",
            )

    subtask = None
    if body.subtask_id is not None:
        subtask = subtask_repo.get(body.subtask_id)
        if subtask is None:
            raise HTTPException(status_code=404, detail="Subtask not found")
        if subtask.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="Subtask does not belong to project",
            )

    tool_run = None
    if body.tool_run_id is not None:
        tool_run = tool_run_repo.get(body.tool_run_id)
        if tool_run is None:
            raise HTTPException(status_code=404, detail="ToolRun not found")

    safety_profile = repo_safety_profile_repo.get_by_repo(repo_obj.id)

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

    generated_title, generated_body = build_pr_draft_content(
        project=project,
        code_repository=repo_obj,
        safety_profile=safety_profile,
        dev_task=dev_task,
        subtask=subtask,
        requirement=requirement,
        epic=epic,
        tool_run=tool_run,
        check_runs=check_runs,
    )

    title = body.title.strip() if body.title else generated_title
    if not title:
        title = generated_title
    pr_body = body.body if body.body is not None else generated_body
    source_branch = body.source_branch or derive_source_branch(dev_task, subtask)

    now = datetime.now(timezone.utc)
    draft = PullRequestDraft(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=repo_obj.id,
        dev_task_id=body.dev_task_id,
        subtask_id=body.subtask_id,
        tool_run_id=body.tool_run_id,
        title=title,
        body=pr_body,
        source_branch=source_branch,
        target_branch=body.target_branch or "main",
        status="draft_prepared",
        provider=body.provider,
        external_pr_url=None,
        external_pr_number=None,
        created_by=current_user or "system",
        error_message=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
    )
    pr_draft_repo.save(draft)
    audit_writer.write(
        "pr_draft_prepared", "pr_draft", draft.id,
        project_id=project_id, actor_email=current_user,
        details={
            "pr_draft_id": draft.id,
            "dev_task_id": draft.dev_task_id,
            "subtask_id": draft.subtask_id,
            "tool_run_id": draft.tool_run_id,
            "code_repository_id": draft.code_repository_id,
            "provider": draft.provider,
        },
    )
    return draft


@router.get("/projects/{project_id}/pr-drafts", response_model=list[PullRequestDraft])
def list_project_pr_drafts(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pr_draft_repo.list_by_project(project_id)


@router.get("/pr-drafts/{pr_draft_id}", response_model=PullRequestDraft)
def get_pr_draft(pr_draft_id: str, _: str = Depends(require_auth)):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return draft


@router.patch("/pr-drafts/{pr_draft_id}", response_model=PullRequestDraft)
def patch_pr_draft(
    pr_draft_id: str,
    body: PullRequestDraftUpdate,
    current_user: str = Depends(require_auth),
):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return draft
    if "status" in patch and patch["status"] is not None:
        target = patch["status"]
        if target == "approved_for_creation":
            raise HTTPException(
                status_code=400,
                detail="Use POST /pr-drafts/{id}/approve to set approved_for_creation",
            )
        if not is_allowed_status_transition(draft.status, target):
            raise HTTPException(
                status_code=400,
                detail=f"Disallowed status transition: {draft.status} -> {target}",
            )
    updated = draft.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    pr_draft_repo.update(updated)
    audit_writer.write(
        "pr_draft_updated", "pr_draft", draft.id,
        project_id=draft.project_id, actor_email=current_user,
        details={"pr_draft_id": draft.id, "changed_fields": list(patch.keys())},
    )
    return updated


@router.post("/pr-drafts/{pr_draft_id}/approve", response_model=PullRequestDraft)
def approve_pr_draft(
    pr_draft_id: str,
    current_user: str = Depends(require_auth),
):
    draft = pr_draft_repo.get(pr_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    if draft.status not in ("draft_prepared", "awaiting_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"PullRequestDraft in status {draft.status!r} cannot be approved",
        )
    now = datetime.now(timezone.utc)
    updated = draft.model_copy(
        update={
            "status": "approved_for_creation",
            "approved_at": now,
            "updated_at": now,
        }
    )
    pr_draft_repo.update(updated)
    audit_writer.write(
        "pr_draft_approved", "pr_draft", draft.id,
        project_id=draft.project_id, actor_email=current_user,
        details={"pr_draft_id": draft.id},
    )
    return updated
