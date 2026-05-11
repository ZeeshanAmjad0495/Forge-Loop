"""Incident triage analysis and remediation-draft preparation.

Owns five audit events: `incident_analysis_requested`,
`incident_analysis_completed`, `incident_analysis_failed`, and
`remediation_work_item_prepared`. Failure handling preserved exactly:
exception → `IncidentAnalysis(status="failed", ...)` returned at HTTP
200.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..incident_triage.agent import run_incident_triage
from ..llm import ProviderError, get_default_provider_name, get_provider_by_name
from ..utils.redaction import redact_sensitive_text
from ..models import (
    Artifact,
    IncidentAnalysis,
    IncidentAnalysisCreate,
    RemediationWorkItemDraft,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    ci_analysis_repo,
    ci_event_repo,
    dev_task_repo,
    incident_analysis_repo,
    incident_repo,
    pr_draft_repo,
    pr_review_repo,
    project_context_repo,
    subtask_repo,
)


def create_analysis(
    incident_id: str,
    body: IncidentAnalysisCreate | None,
    current_user: str,
) -> IncidentAnalysis:
    incident = incident_repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ci_event = ci_event_repo.get(incident.ci_event_id) if incident.ci_event_id else None
    ci_analysis_latest = None
    if ci_event is not None:
        analyses = ci_analysis_repo.list_by_ci_event(ci_event.id)
        ci_analysis_latest = next(
            (a for a in analyses if a.status == "completed"),
            analyses[0] if analyses else None,
        )
    pr_draft = pr_draft_repo.get(incident.pr_draft_id) if incident.pr_draft_id else None
    pr_review_latest = None
    if pr_draft is not None:
        reviews = pr_review_repo.list_by_pr_draft(pr_draft.id)
        pr_review_latest = reviews[0] if reviews else None
    dev_task = dev_task_repo.get(incident.dev_task_id) if incident.dev_task_id else None
    subtask = subtask_repo.get(incident.subtask_id) if incident.subtask_id else None
    project_context = project_context_repo.get(incident.project_id)

    analysis_id = str(uuid.uuid4())
    audit_writer.write(
        "incident_analysis_requested", "incident_analysis", analysis_id,
        project_id=incident.project_id, actor_email=current_user,
        details={
            "incident_id": incident.id,
            "provider": provider.provider_name,
        },
    )

    now = datetime.now(timezone.utc)
    try:
        parsed = run_incident_triage(
            incident=incident,
            provider=provider,
            project_context=project_context,
            ci_event=ci_event,
            ci_analysis=ci_analysis_latest,
            pr_draft=pr_draft,
            pr_review=pr_review_latest,
            dev_task=dev_task,
            subtask=subtask,
            check_run=None,
        )
    except Exception as exc:
        failed = IncidentAnalysis(
            id=analysis_id,
            project_id=incident.project_id,
            incident_id=incident.id,
            provider=provider.provider_name,
            model=provider.model_name,
            status="failed",
            conclusion="unknown",
            summary="",
            impact_assessment=None,
            likely_root_causes=[],
            immediate_actions=[],
            remediation_plan=[],
            prevention_actions=[],
            affected_areas=[],
            recommended_next_action=None,
            raw_output=None,
            artifact_id=None,
            error_message=str(exc),
            created_at=now,
            updated_at=now,
        )
        incident_analysis_repo.save(failed)
        audit_writer.write(
            "incident_analysis_failed", "incident_analysis", failed.id,
            project_id=incident.project_id, actor_email=current_user,
            details={
                "incident_id": incident.id,
                "provider": provider.provider_name,
                "error": redact_sensitive_text(str(exc)),
            },
        )
        return failed

    raw_output = parsed.get("raw_output")
    linked_artifact_id: str | None = None
    if raw_output:
        linked_artifact_id = str(uuid.uuid4())
        artifact_repo.save(Artifact(
            id=linked_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="incident_analysis",
            content=raw_output,
            created_at=now,
        ))
    analysis = IncidentAnalysis(
        id=analysis_id,
        project_id=incident.project_id,
        incident_id=incident.id,
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        conclusion=parsed.get("conclusion") or "unknown",
        summary=parsed.get("summary", ""),
        impact_assessment=parsed.get("impact_assessment"),
        likely_root_causes=list(parsed.get("likely_root_causes") or []),
        immediate_actions=list(parsed.get("immediate_actions") or []),
        remediation_plan=list(parsed.get("remediation_plan") or []),
        prevention_actions=list(parsed.get("prevention_actions") or []),
        affected_areas=list(parsed.get("affected_areas") or []),
        recommended_next_action=parsed.get("recommended_next_action"),
        raw_output=raw_output,
        artifact_id=linked_artifact_id,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    incident_analysis_repo.save(analysis)
    audit_writer.write(
        "incident_analysis_completed", "incident_analysis", analysis.id,
        project_id=incident.project_id, actor_email=current_user,
        details={
            "incident_id": incident.id,
            "provider": analysis.provider,
            "conclusion": analysis.conclusion,
        },
    )
    return analysis


def prepare_remediation(incident_id: str, current_user: str) -> RemediationWorkItemDraft:
    incident = incident_repo.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    analyses = incident_analysis_repo.list_by_incident(incident_id)
    latest = next((a for a in analyses if a.status == "completed"), None)

    title = f"Remediation: {incident.title}"
    description_lines = [
        f"Prepared from incident {incident.id} (severity: {incident.severity}, source: {incident.source}).",
        "",
        "This is a draft remediation work item. A human must review, scope, and",
        "approve it before any coding runner picks it up. ForgeLoop did not",
        "create a DevTask, branch, PR, or deployment automatically.",
        "",
        f"Incident summary: {incident.description}",
    ]
    suggested_acceptance: list[str] = []
    if latest is not None:
        if latest.summary:
            description_lines += ["", "Triage summary:", latest.summary]
        if latest.remediation_plan:
            description_lines += ["", "Suggested remediation plan:"]
            description_lines += [f"- {step}" for step in latest.remediation_plan]
            suggested_acceptance = list(latest.remediation_plan)
        if latest.prevention_actions:
            description_lines += ["", "Suggested prevention actions:"]
            description_lines += [f"- {step}" for step in latest.prevention_actions]

    now = datetime.now(timezone.utc)
    incident.status = "remediation_planned"
    incident.updated_at = now
    incident_repo.save(incident)

    draft = RemediationWorkItemDraft(
        incident_id=incident.id,
        project_id=incident.project_id,
        analysis_id=latest.id if latest else None,
        title=title,
        description="\n".join(description_lines),
        suggested_acceptance_criteria=suggested_acceptance,
        requires_human_approval=True,
        created_at=now,
    )
    audit_writer.write(
        "remediation_work_item_prepared", "incident", incident.id,
        project_id=incident.project_id, actor_email=current_user,
        details={
            "incident_id": incident.id,
            "analysis_id": draft.analysis_id,
        },
    )
    return draft
