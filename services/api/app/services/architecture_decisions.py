"""Architecture Decision Records service (Release 11, Task 67).

Stores ADRs and transitions between their statuses (proposed, accepted,
rejected, deprecated, superseded). The service does NOT apply decisions to
code — it preserves long-term decision memory only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    ADRStatus,
    ArchitectureDecisionRecord,
    ArchitectureDecisionRecordCreate,
    ArchitectureDecisionRecordUpdate,
)
from ..repositories import ArchitectureDecisionRecordRepository

_ALLOWED_TRANSITIONS: dict[ADRStatus, set[ADRStatus]] = {
    "proposed": {"accepted", "rejected"},
    "accepted": {"deprecated", "superseded"},
    "rejected": {"proposed"},
    "deprecated": {"superseded"},
    "superseded": set(),
}


class InvalidADRTransition(ValueError):
    """Raised when an unsupported status transition is requested."""


def _ensure_transition(adr: ArchitectureDecisionRecord, new_status: ADRStatus) -> None:
    if new_status == adr.status:
        return
    if new_status not in _ALLOWED_TRANSITIONS[adr.status]:
        raise InvalidADRTransition(
            f"Cannot transition {adr.status!r} -> {new_status!r}"
        )


def create_adr(
    repo: ArchitectureDecisionRecordRepository,
    *,
    body: ArchitectureDecisionRecordCreate,
) -> ArchitectureDecisionRecord:
    now = datetime.now(timezone.utc)
    adr = ArchitectureDecisionRecord(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        proposal_id=body.proposal_id,
        title=body.title,
        status="proposed",
        context=body.context,
        decision=body.decision,
        consequences=body.consequences,
        alternatives_considered=list(body.alternatives_considered),
        related_source_ids=list(body.related_source_ids),
        related_brief_ids=list(body.related_brief_ids),
        related_review_ids=list(body.related_review_ids),
        tags=list(body.tags),
        created_at=now,
        updated_at=now,
    )
    repo.save(adr)
    return adr


def update_adr(
    repo: ArchitectureDecisionRecordRepository,
    adr: ArchitectureDecisionRecord,
    body: ArchitectureDecisionRecordUpdate,
) -> ArchitectureDecisionRecord:
    data = adr.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ArchitectureDecisionRecord(**data)
    repo.update(updated)
    return updated


def _transition(
    repo: ArchitectureDecisionRecordRepository,
    adr: ArchitectureDecisionRecord,
    new_status: ADRStatus,
    *,
    superseded_by_id: str | None = None,
) -> ArchitectureDecisionRecord:
    _ensure_transition(adr, new_status)
    now = datetime.now(timezone.utc)
    data = adr.model_dump()
    data["status"] = new_status
    data["updated_at"] = now
    if new_status in {"accepted", "rejected"} and not data.get("decided_at"):
        data["decided_at"] = now
    if new_status == "superseded":
        data["superseded_by_id"] = superseded_by_id
    updated = ArchitectureDecisionRecord(**data)
    repo.update(updated)
    return updated


def accept_adr(
    repo: ArchitectureDecisionRecordRepository, adr: ArchitectureDecisionRecord
) -> ArchitectureDecisionRecord:
    return _transition(repo, adr, "accepted")


def reject_adr(
    repo: ArchitectureDecisionRecordRepository, adr: ArchitectureDecisionRecord
) -> ArchitectureDecisionRecord:
    return _transition(repo, adr, "rejected")


def deprecate_adr(
    repo: ArchitectureDecisionRecordRepository, adr: ArchitectureDecisionRecord
) -> ArchitectureDecisionRecord:
    return _transition(repo, adr, "deprecated")


def supersede_adr(
    repo: ArchitectureDecisionRecordRepository,
    adr: ArchitectureDecisionRecord,
    superseded_by_id: str,
) -> ArchitectureDecisionRecord:
    return _transition(
        repo, adr, "superseded", superseded_by_id=superseded_by_id
    )
