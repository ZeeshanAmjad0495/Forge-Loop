"""CI analysis orchestration.

Owns the four `ci_*` audit events. The agent module
(`ci_analysis/agent.py`) remains the LLM/prompt boundary.

Failure handling preserved exactly: any `Exception` from
`run_ci_failure_analysis` becomes a `CIAnalysis(status="failed", ...)`
persisted row and returned at HTTP 200 (not 5xx).
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..ci_analysis.agent import run_ci_failure_analysis
from ..llm import ProviderError, get_default_provider_name, get_provider_by_name
from ..models import CIAnalysis, CIAnalysisCreate
from ..repositories_state import (
    audit_writer,
    check_run_repo,
    ci_analysis_repo,
    ci_event_repo,
    dev_task_repo,
    pr_draft_repo,
    project_context_repo,
    subtask_repo,
)


def create_analysis(
    ci_event_id: str,
    body: CIAnalysisCreate | None,
    current_user: str,
) -> CIAnalysis:
    event = ci_event_repo.get(ci_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="CIEvent not found")

    provider_name = body.provider if (body and body.provider) else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pr_draft = pr_draft_repo.get(event.pr_draft_id) if event.pr_draft_id else None
    dev_task = dev_task_repo.get(event.dev_task_id) if event.dev_task_id else None
    subtask = subtask_repo.get(event.subtask_id) if event.subtask_id else None
    check_run = check_run_repo.get(event.check_run_id) if event.check_run_id else None
    project_context = project_context_repo.get(event.project_id)

    analysis_id = str(uuid.uuid4())
    audit_writer.write(
        "ci_analysis_requested", "ci_analysis", analysis_id,
        project_id=event.project_id, actor_email=current_user,
        details={
            "ci_event_id": event.id,
            "provider": provider.provider_name,
        },
    )

    now = datetime.now(timezone.utc)
    try:
        parsed = run_ci_failure_analysis(
            ci_event=event,
            provider=provider,
            project_context=project_context,
            pr_draft=pr_draft,
            dev_task=dev_task,
            subtask=subtask,
            check_run=check_run,
        )
    except Exception as exc:
        failed = CIAnalysis(
            id=analysis_id,
            project_id=event.project_id,
            ci_event_id=event.id,
            provider=provider.provider_name,
            model=provider.model_name,
            status="failed",
            conclusion="unknown",
            summary="",
            likely_root_causes=[],
            suggested_fixes=[],
            affected_areas=[],
            recommended_next_action=None,
            raw_output=None,
            artifact_id=None,
            error_message=str(exc),
            created_at=now,
            updated_at=now,
        )
        ci_analysis_repo.save(failed)
        audit_writer.write(
            "ci_analysis_failed", "ci_analysis", failed.id,
            project_id=event.project_id, actor_email=current_user,
            details={
                "ci_event_id": event.id,
                "provider": provider.provider_name,
                "error": str(exc),
            },
        )
        return failed

    analysis = CIAnalysis(
        id=analysis_id,
        project_id=event.project_id,
        ci_event_id=event.id,
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        conclusion=parsed.get("conclusion") or "unknown",
        summary=parsed.get("summary", ""),
        likely_root_causes=list(parsed.get("likely_root_causes") or []),
        suggested_fixes=list(parsed.get("suggested_fixes") or []),
        affected_areas=list(parsed.get("affected_areas") or []),
        recommended_next_action=parsed.get("recommended_next_action"),
        raw_output=parsed.get("raw_output"),
        artifact_id=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    ci_analysis_repo.save(analysis)
    audit_writer.write(
        "ci_analysis_completed", "ci_analysis", analysis.id,
        project_id=event.project_id, actor_email=current_user,
        details={
            "ci_event_id": event.id,
            "provider": analysis.provider,
            "conclusion": analysis.conclusion,
        },
    )
    return analysis
