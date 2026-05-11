"""Project memory learning loop orchestration.

Owns seven audit events: `memory_learning_requested`,
`memory_learning_completed`, `memory_learning_failed`,
`memory_candidate_created`, `memory_candidate_approved`,
`memory_candidate_rejected`, and `project_memory_learned`. The agent
module (`memory_learning/agent.py`) is the LLM boundary;
`memory_learning/applier.py` is the persistence-side helper.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..llm import ProviderError, get_default_provider_name, get_provider_by_name
from ..memory_learning.agent import run_memory_learning
from ..utils.redaction import redact_sensitive_text
from ..memory_learning.applier import apply_candidate
from ..memory_learning.source_fetch import SUPPORTED_SOURCE_TYPES, fetch_source
from ..models import (
    Artifact,
    MemoryCandidateRejectRequest,
    MemoryLearningRun,
    MemoryLearningRunCreate,
    ProjectMemoryCandidate,
    ProjectMemoryCandidateCreate,
    ProjectMemoryCandidateUpdate,
)
from ..repositories_state import (
    approval_repo,
    artifact_repo,
    audit_writer,
    check_run_repo,
    ci_analysis_repo,
    dev_task_repo,
    incident_analysis_repo,
    memory_candidate_repo,
    memory_learning_run_repo,
    pr_review_repo,
    project_context_repo,
    project_repo,
    subtask_repo,
    tool_run_repo,
)

CANDIDATE_UPDATABLE_FIELDS = {"memory_type", "title", "content", "tags", "confidence"}


def persist_candidate_from_dict(
    *,
    project_id: str,
    learning_run_id: str | None,
    source_type: str,
    source_id: str | None,
    proposed_by: str | None,
    provider_name: str | None,
    model_name: str | None,
    raw: dict,
    actor_email: str | None,
) -> ProjectMemoryCandidate:
    now = datetime.now(timezone.utc)
    candidate_payload = {
        "memory_type": raw["memory_type"],
        "title": raw["title"],
        "content": raw["content"],
        "tags": list(raw.get("tags") or []),
        "confidence": raw.get("confidence"),
    }
    linked_artifact_id = str(uuid.uuid4())
    artifact_repo.save(Artifact(
        id=linked_artifact_id,
        ticket_id=None,
        requirement_id=None,
        agent_run_id=None,
        artifact_type="memory_candidate_batch",
        content=json.dumps(candidate_payload, sort_keys=True),
        created_at=now,
    ))
    candidate = ProjectMemoryCandidate(
        id=str(uuid.uuid4()),
        project_id=project_id,
        learning_run_id=learning_run_id,
        source_type=source_type,
        source_id=source_id,
        memory_type=raw["memory_type"],
        title=raw["title"],
        content=raw["content"],
        tags=list(raw.get("tags") or []),
        confidence=raw.get("confidence"),
        status="proposed",
        proposed_by=proposed_by,
        provider=provider_name,
        model=model_name,
        artifact_id=linked_artifact_id,
        rejection_reason=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
        rejected_at=None,
    )
    memory_candidate_repo.save(candidate)
    audit_writer.write(
        "memory_candidate_created", "memory_candidate", candidate.id,
        project_id=project_id, actor_email=actor_email,
        details={
            "memory_type": candidate.memory_type,
            "source_type": candidate.source_type,
            "source_id": candidate.source_id,
            "learning_run_id": candidate.learning_run_id,
        },
    )
    return candidate


def create_run(project_id: str, body: MemoryLearningRunCreate, current_user: str) -> MemoryLearningRun:
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"source_type {body.source_type!r} is not supported as a "
                "learning-run input"
            ),
        )

    try:
        fetched = fetch_source(
            body.source_type, body.source_id,
            ci_analysis_repo=ci_analysis_repo,
            incident_analysis_repo=incident_analysis_repo,
            pr_review_repo=pr_review_repo,
            check_run_repo=check_run_repo,
            tool_run_repo=tool_run_repo,
            approval_repo=approval_repo,
            dev_task_repo=dev_task_repo,
            subtask_repo=subtask_repo,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if fetched is None:
        raise HTTPException(status_code=404, detail="Source not found")
    source_obj, source_block = fetched

    provider_name = body.provider if body.provider else get_default_provider_name()
    try:
        provider = get_provider_by_name(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    project_context = project_context_repo.get(project_id)
    run_id = str(uuid.uuid4())
    audit_writer.write(
        "memory_learning_requested", "memory_learning_run", run_id,
        project_id=project_id, actor_email=current_user,
        details={
            "source_type": body.source_type,
            "source_id": body.source_id,
            "provider": provider.provider_name,
        },
    )

    now = datetime.now(timezone.utc)
    try:
        result = run_memory_learning(
            provider=provider,
            project_context=project_context,
            source_type=body.source_type,
            source_summary_block=source_block,
        )
    except Exception as exc:
        failed = MemoryLearningRun(
            id=run_id,
            project_id=project_id,
            source_type=body.source_type,
            source_id=body.source_id,
            provider=provider.provider_name,
            model=provider.model_name,
            status="failed",
            summary="",
            candidates_created=0,
            candidate_ids=[],
            artifact_id=None,
            raw_output=None,
            error_message=str(exc),
            created_at=now,
            updated_at=now,
        )
        memory_learning_run_repo.save(failed)
        audit_writer.write(
            "memory_learning_failed", "memory_learning_run", failed.id,
            project_id=project_id, actor_email=current_user,
            details={
                "source_type": body.source_type,
                "source_id": body.source_id,
                "provider": provider.provider_name,
                "error": redact_sensitive_text(str(exc)),
            },
        )
        return failed

    candidate_ids: list[str] = []
    for raw_candidate in result.get("candidates") or []:
        candidate = persist_candidate_from_dict(
            project_id=project_id,
            learning_run_id=run_id,
            source_type=body.source_type,
            source_id=body.source_id,
            proposed_by=current_user,
            provider_name=provider.provider_name,
            model_name=provider.model_name,
            raw=raw_candidate,
            actor_email=current_user,
        )
        candidate_ids.append(candidate.id)

    summary_text = result.get("summary") or ""
    raw_output = result.get("raw_output")
    run_artifact_id: str | None = None
    summary_content = raw_output or summary_text
    if summary_content:
        run_artifact_id = str(uuid.uuid4())
        artifact_repo.save(Artifact(
            id=run_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="memory_learning_summary",
            content=summary_content,
            created_at=now,
        ))
    run = MemoryLearningRun(
        id=run_id,
        project_id=project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        summary=summary_text,
        candidates_created=len(candidate_ids),
        candidate_ids=candidate_ids,
        artifact_id=run_artifact_id,
        raw_output=raw_output,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    memory_learning_run_repo.save(run)
    audit_writer.write(
        "memory_learning_completed", "memory_learning_run", run.id,
        project_id=project_id, actor_email=current_user,
        details={
            "source_type": body.source_type,
            "source_id": body.source_id,
            "provider": provider.provider_name,
            "candidates_created": len(candidate_ids),
        },
    )
    return run


def create_manual_candidate(
    project_id: str,
    body: ProjectMemoryCandidateCreate,
    current_user: str,
) -> ProjectMemoryCandidate:
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return persist_candidate_from_dict(
        project_id=project_id,
        learning_run_id=body.learning_run_id,
        source_type=body.source_type,
        source_id=body.source_id,
        proposed_by=body.proposed_by or current_user,
        provider_name=body.provider,
        model_name=body.model,
        raw={
            "memory_type": body.memory_type,
            "title": body.title,
            "content": body.content,
            "tags": body.tags,
            "confidence": body.confidence,
        },
        actor_email=current_user,
    )


def update_candidate(
    candidate_id: str,
    body: ProjectMemoryCandidateUpdate,
) -> ProjectMemoryCandidate:
    candidate = memory_candidate_repo.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="MemoryCandidate not found")
    if candidate.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail="Candidate is not in 'proposed' status; PATCH not allowed",
        )

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field not in CANDIDATE_UPDATABLE_FIELDS:
            continue
        setattr(candidate, field, value)

    candidate.updated_at = datetime.now(timezone.utc)
    memory_candidate_repo.save(candidate)
    return candidate


def approve_candidate(candidate_id: str, current_user: str) -> ProjectMemoryCandidate:
    candidate = memory_candidate_repo.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="MemoryCandidate not found")
    if candidate.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail="Candidate is not in 'proposed' status; cannot approve",
        )

    context = project_context_repo.get(candidate.project_id)
    updated_context = apply_candidate(context, candidate)
    project_context_repo.save(updated_context)

    now = datetime.now(timezone.utc)
    candidate.status = "approved"
    candidate.approved_at = now
    candidate.updated_at = now
    memory_candidate_repo.save(candidate)

    audit_writer.write(
        "memory_candidate_approved", "memory_candidate", candidate.id,
        project_id=candidate.project_id, actor_email=current_user,
        details={
            "memory_type": candidate.memory_type,
            "source_type": candidate.source_type,
            "source_id": candidate.source_id,
        },
    )
    audit_writer.write(
        "project_memory_learned", "project_context", candidate.project_id,
        project_id=candidate.project_id, actor_email=current_user,
        details={
            "candidate_id": candidate.id,
            "memory_type": candidate.memory_type,
        },
    )
    return candidate


def reject_candidate(
    candidate_id: str,
    body: MemoryCandidateRejectRequest | None,
    current_user: str,
) -> ProjectMemoryCandidate:
    candidate = memory_candidate_repo.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="MemoryCandidate not found")
    if candidate.status != "proposed":
        raise HTTPException(
            status_code=409,
            detail="Candidate is not in 'proposed' status; cannot reject",
        )

    reason = body.reason if body else None
    now = datetime.now(timezone.utc)
    candidate.status = "rejected"
    candidate.rejection_reason = reason
    candidate.rejected_at = now
    candidate.updated_at = now
    memory_candidate_repo.save(candidate)

    audit_writer.write(
        "memory_candidate_rejected", "memory_candidate", candidate.id,
        project_id=candidate.project_id, actor_email=current_user,
        details={
            "memory_type": candidate.memory_type,
            "reason": reason,
        },
    )
    return candidate
