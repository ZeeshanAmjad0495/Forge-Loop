from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ImprovementProposal,
    ImprovementProposalCreate,
    ImprovementProposalRejectRequest,
    ImprovementProposalUpdate,
)
from ..repositories_state import (
    architecture_review_repo,
    audit_writer,
    improvement_proposal_repo,
    project_repo,
    research_brief_repo,
)
from ..services.improvement_proposals import (
    InvalidProposalTransition,
    approve_proposal,
    archive_proposal,
    create_proposal,
    defer_proposal,
    mark_implemented,
    reject_proposal,
    update_proposal,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _get_or_404(proposal_id: str) -> ImprovementProposal:
    proposal = improvement_proposal_repo.get(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=404, detail="Improvement proposal not found"
        )
    return proposal


@router.post(
    "/improvement-proposals",
    response_model=ImprovementProposal,
    status_code=201,
)
def create_improvement_proposal(
    body: ImprovementProposalCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    proposal = create_proposal(improvement_proposal_repo, body=body)
    audit_writer.write(
        action="improvement_proposal_created",
        target_type="improvement_proposal",
        target_id=proposal.id,
        project_id=proposal.project_id,
        actor_email=current_user,
        details={
            "proposal_type": proposal.proposal_type,
            "source_type": proposal.source_type,
            "priority": proposal.priority,
        },
    )
    return proposal


@router.get(
    "/improvement-proposals",
    response_model=list[ImprovementProposal],
)
def list_improvement_proposals(
    project_id: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    proposal_type: str | None = None,
    current_user: str = Depends(require_auth),
):
    if source_type is not None and source_id is not None:
        items = improvement_proposal_repo.list_by_source(source_type, source_id)
    elif project_id is not None:
        _ensure_project(project_id)
        items = improvement_proposal_repo.list_by_project(project_id)
    else:
        items = improvement_proposal_repo.list_all()
    if status is not None:
        items = [p for p in items if p.status == status]
    if priority is not None:
        items = [p for p in items if p.priority == priority]
    if proposal_type is not None:
        items = [p for p in items if p.proposal_type == proposal_type]
    if source_type is not None and source_id is None:
        items = [p for p in items if p.source_type == source_type]
    return items


@router.get(
    "/projects/{project_id}/improvement-proposals",
    response_model=list[ImprovementProposal],
)
def list_improvement_proposals_for_project(
    project_id: str,
    status: str | None = None,
    priority: str | None = None,
    proposal_type: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = improvement_proposal_repo.list_by_project(project_id)
    if status is not None:
        items = [p for p in items if p.status == status]
    if priority is not None:
        items = [p for p in items if p.priority == priority]
    if proposal_type is not None:
        items = [p for p in items if p.proposal_type == proposal_type]
    return items


@router.get(
    "/improvement-proposals/{proposal_id}",
    response_model=ImprovementProposal,
)
def get_improvement_proposal(
    proposal_id: str,
    current_user: str = Depends(require_auth),
):
    return _get_or_404(proposal_id)


@router.patch(
    "/improvement-proposals/{proposal_id}",
    response_model=ImprovementProposal,
)
def patch_improvement_proposal(
    proposal_id: str,
    body: ImprovementProposalUpdate,
    current_user: str = Depends(require_auth),
):
    proposal = _get_or_404(proposal_id)
    updated = update_proposal(improvement_proposal_repo, proposal, body)
    audit_writer.write(
        action="improvement_proposal_updated",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


def _try_transition(fn, proposal: ImprovementProposal, *args, **kwargs):
    try:
        return fn(improvement_proposal_repo, proposal, *args, **kwargs)
    except InvalidProposalTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/improvement-proposals/{proposal_id}/approve",
    response_model=ImprovementProposal,
)
def approve(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    proposal = _get_or_404(proposal_id)
    updated = _try_transition(approve_proposal, proposal)
    audit_writer.write(
        action="improvement_proposal_approved",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/improvement-proposals/{proposal_id}/reject",
    response_model=ImprovementProposal,
)
def reject(
    proposal_id: str,
    body: ImprovementProposalRejectRequest | None = None,
    current_user: str = Depends(require_auth),
):
    proposal = _get_or_404(proposal_id)
    reason = body.reason if body else ""
    updated = _try_transition(reject_proposal, proposal, reason=reason)
    audit_writer.write(
        action="improvement_proposal_rejected",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"reason": reason},
    )
    return updated


@router.post(
    "/improvement-proposals/{proposal_id}/defer",
    response_model=ImprovementProposal,
)
def defer(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    proposal = _get_or_404(proposal_id)
    updated = _try_transition(defer_proposal, proposal)
    audit_writer.write(
        action="improvement_proposal_deferred",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/improvement-proposals/{proposal_id}/mark-implemented",
    response_model=ImprovementProposal,
)
def mark_implemented_route(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    proposal = _get_or_404(proposal_id)
    updated = _try_transition(mark_implemented, proposal)
    audit_writer.write(
        action="improvement_proposal_implemented",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/improvement-proposals/{proposal_id}/archive",
    response_model=ImprovementProposal,
)
def archive(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    proposal = _get_or_404(proposal_id)
    updated = _try_transition(archive_proposal, proposal)
    audit_writer.write(
        action="improvement_proposal_archived",
        target_type="improvement_proposal",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


# -- source-derived helpers ----------------------------------------------


@router.post(
    "/research-briefs/{brief_id}/improvement-proposals",
    response_model=ImprovementProposal,
    status_code=201,
)
def create_proposal_from_brief(
    brief_id: str,
    body: ImprovementProposalCreate,
    current_user: str = Depends(require_auth),
):
    brief = research_brief_repo.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Research brief not found")
    payload = body.model_copy(
        update={
            "source_type": "research_brief",
            "source_id": brief_id,
            "project_id": body.project_id or brief.project_id,
        }
    )
    _ensure_project(payload.project_id)
    proposal = create_proposal(improvement_proposal_repo, body=payload)
    audit_writer.write(
        action="improvement_proposal_created",
        target_type="improvement_proposal",
        target_id=proposal.id,
        project_id=proposal.project_id,
        actor_email=current_user,
        details={"source_type": "research_brief", "source_id": brief_id},
    )
    return proposal


@router.post(
    "/architecture-reviews/{review_id}/improvement-proposals",
    response_model=ImprovementProposal,
    status_code=201,
)
def create_proposal_from_review(
    review_id: str,
    body: ImprovementProposalCreate,
    current_user: str = Depends(require_auth),
):
    review = architecture_review_repo.get(review_id)
    if review is None:
        raise HTTPException(
            status_code=404, detail="Architecture review not found"
        )
    payload = body.model_copy(
        update={
            "source_type": "architecture_review",
            "source_id": review_id,
            "project_id": body.project_id or review.project_id,
        }
    )
    _ensure_project(payload.project_id)
    proposal = create_proposal(improvement_proposal_repo, body=payload)
    audit_writer.write(
        action="improvement_proposal_created",
        target_type="improvement_proposal",
        target_id=proposal.id,
        project_id=proposal.project_id,
        actor_email=current_user,
        details={"source_type": "architecture_review", "source_id": review_id},
    )
    return proposal
