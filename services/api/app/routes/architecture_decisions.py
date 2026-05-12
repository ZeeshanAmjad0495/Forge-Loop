from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ArchitectureDecisionRecord,
    ArchitectureDecisionRecordCreate,
    ArchitectureDecisionRecordUpdate,
    ArchitectureDecisionSupersedeRequest,
)
from ..repositories_state import (
    architecture_decision_repo,
    audit_writer,
    improvement_proposal_repo,
    project_repo,
)
from ..services.architecture_decisions import (
    InvalidADRTransition,
    accept_adr,
    create_adr,
    deprecate_adr,
    reject_adr,
    supersede_adr,
    update_adr,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _get_or_404(adr_id: str) -> ArchitectureDecisionRecord:
    adr = architecture_decision_repo.get(adr_id)
    if adr is None:
        raise HTTPException(
            status_code=404, detail="Architecture decision not found"
        )
    return adr


def _try(fn, *args, **kwargs):
    try:
        return fn(architecture_decision_repo, *args, **kwargs)
    except InvalidADRTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/architecture-decisions",
    response_model=ArchitectureDecisionRecord,
    status_code=201,
)
def create_architecture_decision(
    body: ArchitectureDecisionRecordCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    adr = create_adr(architecture_decision_repo, body=body)
    audit_writer.write(
        action="architecture_decision_created",
        target_type="architecture_decision",
        target_id=adr.id,
        project_id=adr.project_id,
        actor_email=current_user,
    )
    return adr


@router.get(
    "/architecture-decisions",
    response_model=list[ArchitectureDecisionRecord],
)
def list_architecture_decisions(
    project_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    current_user: str = Depends(require_auth),
):
    if proposal_id is not None:
        items = architecture_decision_repo.list_by_proposal(proposal_id)
    elif project_id is not None:
        _ensure_project(project_id)
        items = architecture_decision_repo.list_by_project(project_id)
    else:
        items = architecture_decision_repo.list_all()
    if status is not None:
        items = [a for a in items if a.status == status]
    if tag is not None:
        items = [a for a in items if tag in a.tags]
    return items


@router.get(
    "/projects/{project_id}/architecture-decisions",
    response_model=list[ArchitectureDecisionRecord],
)
def list_architecture_decisions_for_project(
    project_id: str,
    status: str | None = None,
    tag: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = architecture_decision_repo.list_by_project(project_id)
    if status is not None:
        items = [a for a in items if a.status == status]
    if tag is not None:
        items = [a for a in items if tag in a.tags]
    return items


@router.get(
    "/architecture-decisions/{adr_id}",
    response_model=ArchitectureDecisionRecord,
)
def get_architecture_decision(
    adr_id: str,
    current_user: str = Depends(require_auth),
):
    return _get_or_404(adr_id)


@router.patch(
    "/architecture-decisions/{adr_id}",
    response_model=ArchitectureDecisionRecord,
)
def patch_architecture_decision(
    adr_id: str,
    body: ArchitectureDecisionRecordUpdate,
    current_user: str = Depends(require_auth),
):
    adr = _get_or_404(adr_id)
    updated = update_adr(architecture_decision_repo, adr, body)
    audit_writer.write(
        action="architecture_decision_updated",
        target_type="architecture_decision",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/architecture-decisions/{adr_id}/accept",
    response_model=ArchitectureDecisionRecord,
)
def accept(adr_id: str, current_user: str = Depends(require_auth)):
    adr = _get_or_404(adr_id)
    updated = _try(accept_adr, adr)
    audit_writer.write(
        action="architecture_decision_accepted",
        target_type="architecture_decision",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/architecture-decisions/{adr_id}/reject",
    response_model=ArchitectureDecisionRecord,
)
def reject(adr_id: str, current_user: str = Depends(require_auth)):
    adr = _get_or_404(adr_id)
    updated = _try(reject_adr, adr)
    audit_writer.write(
        action="architecture_decision_rejected",
        target_type="architecture_decision",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/architecture-decisions/{adr_id}/deprecate",
    response_model=ArchitectureDecisionRecord,
)
def deprecate(adr_id: str, current_user: str = Depends(require_auth)):
    adr = _get_or_404(adr_id)
    updated = _try(deprecate_adr, adr)
    audit_writer.write(
        action="architecture_decision_deprecated",
        target_type="architecture_decision",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/architecture-decisions/{adr_id}/supersede",
    response_model=ArchitectureDecisionRecord,
)
def supersede(
    adr_id: str,
    body: ArchitectureDecisionSupersedeRequest,
    current_user: str = Depends(require_auth),
):
    adr = _get_or_404(adr_id)
    if architecture_decision_repo.get(body.superseded_by_id) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown superseded_by_id: {body.superseded_by_id}",
        )
    updated = _try(supersede_adr, adr, superseded_by_id=body.superseded_by_id)
    audit_writer.write(
        action="architecture_decision_superseded",
        target_type="architecture_decision",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"superseded_by_id": body.superseded_by_id},
    )
    return updated


@router.post(
    "/improvement-proposals/{proposal_id}/architecture-decision",
    response_model=ArchitectureDecisionRecord,
    status_code=201,
)
def create_decision_from_proposal(
    proposal_id: str,
    body: ArchitectureDecisionRecordCreate,
    current_user: str = Depends(require_auth),
):
    proposal = improvement_proposal_repo.get(proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=404, detail="Improvement proposal not found"
        )
    payload = body.model_copy(
        update={
            "proposal_id": proposal_id,
            "project_id": body.project_id or proposal.project_id,
        }
    )
    _ensure_project(payload.project_id)
    adr = create_adr(architecture_decision_repo, body=payload)
    audit_writer.write(
        action="architecture_decision_created",
        target_type="architecture_decision",
        target_id=adr.id,
        project_id=adr.project_id,
        actor_email=current_user,
        details={"from_proposal_id": proposal_id},
    )
    return adr
