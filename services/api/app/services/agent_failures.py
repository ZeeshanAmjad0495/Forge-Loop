"""Agent failure taxonomy (Release 10, Task 60).

Manual classification + summary counters for failures observed in agent /
tool / check / review workflows. Not an automated detector.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone

from ..models import (
    AgentFailureRecord,
    AgentFailureRecordCreate,
    AgentFailureRecordResolve,
    AgentFailureRecordUpdate,
    AgentFailureSummary,
)
from ..repositories import AgentFailureRecordRepository


def create_failure(
    repo: AgentFailureRecordRepository,
    *,
    project_id: str,
    body: AgentFailureRecordCreate,
) -> AgentFailureRecord:
    now = datetime.now(timezone.utc)
    record = AgentFailureRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        trial_id=body.trial_id,
        category=body.category,
        severity=body.severity,
        summary=body.summary,
        details=body.details,
        detected_by=body.detected_by,
        created_at=now,
        updated_at=now,
    )
    repo.save(record)
    return record


def update_failure(
    repo: AgentFailureRecordRepository,
    record: AgentFailureRecord,
    body: AgentFailureRecordUpdate,
) -> AgentFailureRecord:
    data = record.model_dump()
    for field, value in body.model_dump(exclude_unset=True).items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = AgentFailureRecord(**data)
    repo.update(updated)
    return updated


def resolve_failure(
    repo: AgentFailureRecordRepository,
    record: AgentFailureRecord,
    body: AgentFailureRecordResolve,
) -> AgentFailureRecord:
    data = record.model_dump()
    now = datetime.now(timezone.utc)
    data["status"] = body.status
    data["resolution_summary"] = body.resolution_summary
    if body.status in {"resolved", "dismissed"}:
        data["resolved_at"] = now
    data["updated_at"] = now
    updated = AgentFailureRecord(**data)
    repo.update(updated)
    return updated


def summary_for_project(
    repo: AgentFailureRecordRepository, *, project_id: str
) -> AgentFailureSummary:
    items = repo.list_by_project(project_id)
    return AgentFailureSummary(
        project_id=project_id,
        total=len(items),
        by_category=dict(Counter(i.category for i in items)),
        by_severity=dict(Counter(i.severity for i in items)),
        by_status=dict(Counter(i.status for i in items)),
        by_source_type=dict(Counter(i.source_type for i in items)),
    )
