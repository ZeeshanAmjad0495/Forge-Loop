import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    Incident,
    IncidentAnalysis,
    IncidentAnalysisCreate,
    IncidentCreate,
    IncidentUpdate,
    RemediationWorkItemDraft,
)
from ..repositories_state import (
    audit_writer,
    ci_event_repo,
    code_repo_repo,
    dev_task_repo,
    incident_analysis_repo,
    incident_repo,
    pr_draft_repo,
    project_repo,
    subtask_repo,
)
from ..services import incident_analysis_workflow

router = APIRouter()


_INCIDENT_UPDATABLE_FIELDS = {
    "title",
    "description",
    "severity",
    "status",
    "source",
    "environment",
    "affected_area",
    "evidence",
    "external_url",
    "resolved_at",
}


@router.post(
    "/projects/{project_id}/incidents",
    response_model=Incident,
    status_code=201,
)
def record_incident(
    project_id: str,
    body: IncidentCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.ci_event_id is not None:
        if ci_event_repo.get(body.ci_event_id) is None:
            raise HTTPException(status_code=404, detail="CIEvent not found")
    if body.pr_draft_id is not None:
        if pr_draft_repo.get(body.pr_draft_id) is None:
            raise HTTPException(status_code=404, detail="PullRequestDraft not found")
    if body.dev_task_id is not None:
        if dev_task_repo.get(body.dev_task_id) is None:
            raise HTTPException(status_code=404, detail="DevTask not found")
    if body.subtask_id is not None:
        if subtask_repo.get(body.subtask_id) is None:
            raise HTTPException(status_code=404, detail="Subtask not found")

    now = datetime.now(timezone.utc)
    incident = Incident(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        ci_event_id=body.ci_event_id,
        pr_draft_id=body.pr_draft_id,
        dev_task_id=body.dev_task_id,
        subtask_id=body.subtask_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        status="reported",
        source=body.source,
        environment=body.environment,
        affected_area=body.affected_area,
        started_at=body.started_at,
        detected_at=body.detected_at,
        resolved_at=None,
        external_url=body.external_url,
        evidence=body.evidence,
        created_at=now,
        updated_at=now,
    )
    incident_repo.save(incident)
    audit_writer.write(
        "incident_recorded", "incident", incident.id,
        project_id=project_id, actor_email=current_user,
        details={
            "severity": incident.severity,
            "source": incident.source,
            "environment": incident.environment,
            "affected_area": incident.affected_area,
            "ci_event_id": incident.ci_event_id,
            "pr_draft_id": incident.pr_draft_id,
            "dev_task_id": incident.dev_task_id,
        },
    )
    return incident


@router.get("/projects/{project_id}/incidents", response_model=list[Incident])
def list_project_incidents(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return incident_repo.list_by_project(project_id)


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str, _: str = Depends(require_auth)):
    incident = incident_repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=Incident)
def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    current_user: str = Depends(require_auth),
):
    incident = incident_repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    changes = body.model_dump(exclude_unset=True)
    applied: dict = {}
    for field, value in changes.items():
        if field not in _INCIDENT_UPDATABLE_FIELDS:
            continue
        setattr(incident, field, value)
        applied[field] = value

    incident.updated_at = datetime.now(timezone.utc)
    incident_repo.save(incident)
    audit_writer.write(
        "incident_updated", "incident", incident.id,
        project_id=incident.project_id, actor_email=current_user,
        details={"changed_fields": sorted(applied.keys())},
    )
    return incident


@router.post(
    "/incidents/{incident_id}/analysis",
    response_model=IncidentAnalysis,
    status_code=201,
)
def create_incident_analysis(
    incident_id: str,
    body: IncidentAnalysisCreate | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    return incident_analysis_workflow.create_analysis(incident_id, body, current_user)


@router.get(
    "/incidents/{incident_id}/analyses",
    response_model=list[IncidentAnalysis],
)
def list_incident_analyses(incident_id: str, _: str = Depends(require_auth)):
    if incident_repo.get(incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident_analysis_repo.list_by_incident(incident_id)


@router.get("/incident-analyses/{analysis_id}", response_model=IncidentAnalysis)
def get_incident_analysis(analysis_id: str, _: str = Depends(require_auth)):
    analysis = incident_analysis_repo.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="IncidentAnalysis not found")
    return analysis


@router.post(
    "/incidents/{incident_id}/prepare-remediation",
    response_model=RemediationWorkItemDraft,
    status_code=201,
)
def prepare_incident_remediation(
    incident_id: str,
    current_user: str = Depends(require_auth),
):
    return incident_analysis_workflow.prepare_remediation(incident_id, current_user)
