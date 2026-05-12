"""Improvement Proposal workflow service (Release 11, Task 66).

Turns research/architecture/retrospective findings into human-approved
improvement proposals. NEVER executes the proposal — no code changes, no
branches, no PRs, no OpenHands invocation. State transitions are explicit
and gated on the caller (eventually a human via the API/UI).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    ImprovementProposal,
    ImprovementProposalCreate,
    ImprovementProposalStatus,
    ImprovementProposalUpdate,
)
from ..repositories import ImprovementProposalRepository

# Allowed status transitions. "archived" is reachable from any non-archived
# state; the other transitions follow the obvious review workflow.
_ALLOWED_TRANSITIONS: dict[ImprovementProposalStatus, set[ImprovementProposalStatus]] = {
    "proposed": {"approved", "rejected", "deferred", "archived"},
    "deferred": {"proposed", "approved", "rejected", "archived"},
    "approved": {"implemented", "rejected", "archived"},
    "rejected": {"proposed", "archived"},
    "implemented": {"archived"},
    "archived": set(),
}


class InvalidProposalTransition(ValueError):
    """Raised when callers attempt an unsupported status transition."""


def _ensure_transition(
    proposal: ImprovementProposal, new_status: ImprovementProposalStatus
) -> None:
    if new_status == proposal.status:
        return
    if new_status not in _ALLOWED_TRANSITIONS[proposal.status]:
        raise InvalidProposalTransition(
            f"Cannot transition {proposal.status!r} -> {new_status!r}"
        )


def create_proposal(
    repo: ImprovementProposalRepository,
    *,
    body: ImprovementProposalCreate,
) -> ImprovementProposal:
    now = datetime.now(timezone.utc)
    proposal = ImprovementProposal(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        title=body.title,
        description=body.description,
        proposal_type=body.proposal_type,
        status="proposed",
        priority=body.priority,
        expected_benefit=body.expected_benefit,
        risk=body.risk,
        implementation_notes=body.implementation_notes,
        affected_areas=list(body.affected_areas),
        created_at=now,
        updated_at=now,
    )
    repo.save(proposal)
    return proposal


def update_proposal(
    repo: ImprovementProposalRepository,
    proposal: ImprovementProposal,
    body: ImprovementProposalUpdate,
) -> ImprovementProposal:
    data = proposal.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ImprovementProposal(**data)
    repo.update(updated)
    return updated


def _transition(
    repo: ImprovementProposalRepository,
    proposal: ImprovementProposal,
    new_status: ImprovementProposalStatus,
    *,
    rejection_reason: str | None = None,
) -> ImprovementProposal:
    _ensure_transition(proposal, new_status)
    now = datetime.now(timezone.utc)
    data = proposal.model_dump()
    data["status"] = new_status
    data["updated_at"] = now
    if new_status == "approved":
        data["approved_at"] = now
    elif new_status == "rejected":
        data["rejected_at"] = now
        data["rejection_reason"] = rejection_reason
    elif new_status == "implemented":
        data["implemented_at"] = now
    updated = ImprovementProposal(**data)
    repo.update(updated)
    return updated


def approve_proposal(
    repo: ImprovementProposalRepository, proposal: ImprovementProposal
) -> ImprovementProposal:
    return _transition(repo, proposal, "approved")


def reject_proposal(
    repo: ImprovementProposalRepository,
    proposal: ImprovementProposal,
    reason: str = "",
) -> ImprovementProposal:
    return _transition(repo, proposal, "rejected", rejection_reason=reason)


def defer_proposal(
    repo: ImprovementProposalRepository, proposal: ImprovementProposal
) -> ImprovementProposal:
    return _transition(repo, proposal, "deferred")


def mark_implemented(
    repo: ImprovementProposalRepository, proposal: ImprovementProposal
) -> ImprovementProposal:
    return _transition(repo, proposal, "implemented")


def archive_proposal(
    repo: ImprovementProposalRepository, proposal: ImprovementProposal
) -> ImprovementProposal:
    return _transition(repo, proposal, "archived")
