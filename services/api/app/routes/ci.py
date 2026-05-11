import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    CIAnalysis,
    CIAnalysisCreate,
    CIEvent,
    CIEventCreate,
)
from ..repositories_state import (
    audit_writer,
    check_run_repo,
    ci_analysis_repo,
    ci_event_repo,
    code_repo_repo,
    dev_task_repo,
    pr_draft_repo,
    project_repo,
    subtask_repo,
)
from ..services import ci_analysis_workflow

router = APIRouter()


@router.post(
    "/projects/{project_id}/ci-events",
    response_model=CIEvent,
    status_code=201,
)
def record_ci_event(
    project_id: str,
    body: CIEventCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.code_repository_id is not None:
        repo_obj = code_repo_repo.get(body.code_repository_id)
        if repo_obj is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.pr_draft_id is not None:
        if pr_draft_repo.get(body.pr_draft_id) is None:
            raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    if body.dev_task_id is not None:
        if dev_task_repo.get(body.dev_task_id) is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
    if body.subtask_id is not None:
        if subtask_repo.get(body.subtask_id) is None:
            raise HTTPException(status_code=404, detail="Subtask not found")
    if body.check_run_id is not None:
        if check_run_repo.get(body.check_run_id) is None:
            raise HTTPException(status_code=404, detail="CheckRun not found")

    now = datetime.now(timezone.utc)
    event = CIEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        pr_draft_id=body.pr_draft_id,
        dev_task_id=body.dev_task_id,
        subtask_id=body.subtask_id,
        check_run_id=body.check_run_id,
        provider=body.provider,
        external_run_id=body.external_run_id,
        workflow_name=body.workflow_name,
        job_name=body.job_name,
        branch=body.branch,
        commit_sha=body.commit_sha,
        pr_number=body.pr_number,
        pr_url=body.pr_url,
        status=body.status,
        conclusion=body.conclusion,
        failure_summary=body.failure_summary,
        logs_excerpt=body.logs_excerpt,
        raw_payload=body.raw_payload,
        artifact_id=None,
        created_at=now,
        updated_at=now,
    )
    ci_event_repo.save(event)
    audit_writer.write(
        "ci_event_recorded", "ci_event", event.id,
        project_id=project_id, actor_email=current_user,
        details={
            "provider": event.provider,
            "workflow_name": event.workflow_name,
            "job_name": event.job_name,
            "conclusion": event.conclusion,
            "pr_draft_id": event.pr_draft_id,
            "dev_task_id": event.dev_task_id,
            "check_run_id": event.check_run_id,
        },
    )
    return event


@router.get("/projects/{project_id}/ci-events", response_model=list[CIEvent])
def list_project_ci_events(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ci_event_repo.list_by_project(project_id)


@router.get("/ci-events/{ci_event_id}", response_model=CIEvent)
def get_ci_event(ci_event_id: str, _: str = Depends(require_auth)):
    event = ci_event_repo.get(ci_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")
    return event


@router.get("/pr-drafts/{pr_draft_id}/ci-events", response_model=list[CIEvent])
def list_pr_draft_ci_events(pr_draft_id: str, _: str = Depends(require_auth)):
    if pr_draft_repo.get(pr_draft_id) is None:
        raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    return ci_event_repo.list_by_pr_draft(pr_draft_id)


@router.post(
    "/ci-events/{ci_event_id}/analysis",
    response_model=CIAnalysis,
    status_code=201,
)
def create_ci_analysis(
    ci_event_id: str,
    body: CIAnalysisCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    return ci_analysis_workflow.create_analysis(ci_event_id, body, current_user)


@router.get("/ci-events/{ci_event_id}/analyses", response_model=list[CIAnalysis])
def list_ci_event_analyses(ci_event_id: str, _: str = Depends(require_auth)):
    if ci_event_repo.get(ci_event_id) is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")
    return ci_analysis_repo.list_by_ci_event(ci_event_id)


@router.get("/ci-analyses/{analysis_id}", response_model=CIAnalysis)
def get_ci_analysis(analysis_id: str, _: str = Depends(require_auth)):
    analysis = ci_analysis_repo.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="CIAnalysis not found")
    return analysis
