from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ImprovementProposal,
    ImprovementProposalCreate,
    ProjectRetrospective,
    ProjectRetrospectiveCreate,
    ProjectRetrospectiveGenerateRequest,
    ProjectRetrospectiveUpdate,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    improvement_proposal_repo,
    project_build_trial_repo,
    project_repo,
    project_retrospective_repo,
)
from ..services.improvement_proposals import create_proposal
from ..services.retrospectives import (
    archive_retrospective,
    create_retrospective,
    generate_retrospective,
    update_retrospective,
)
from .common import resolve_routed_provider_or_400

router = APIRouter()


def _ensure_project(project_id: str) -> None:
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _get_or_404(retro_id: str) -> ProjectRetrospective:
    retro = project_retrospective_repo.get(retro_id)
    if retro is None:
        raise HTTPException(
            status_code=404, detail="Project retrospective not found"
        )
    return retro


@router.post(
    "/projects/{project_id}/retrospectives",
    response_model=ProjectRetrospective,
    status_code=201,
)
def create_project_retrospective(
    project_id: str,
    body: ProjectRetrospectiveCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    if body.trial_id is not None and project_build_trial_repo.get(body.trial_id) is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown trial_id: {body.trial_id}"
        )
    retro = create_retrospective(
        project_retrospective_repo, project_id=project_id, body=body
    )
    audit_writer.write(
        action="project_retrospective_created",
        target_type="project_retrospective",
        target_id=retro.id,
        project_id=retro.project_id,
        actor_email=current_user,
        details={"trial_id": retro.trial_id, "status": retro.status},
    )
    return retro


@router.get(
    "/projects/{project_id}/retrospectives",
    response_model=list[ProjectRetrospective],
)
def list_project_retrospectives(
    project_id: str,
    trial_id: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = project_retrospective_repo.list_by_project(project_id)
    if trial_id is not None:
        items = [r for r in items if r.trial_id == trial_id]
    if status is not None:
        items = [r for r in items if r.status == status]
    return items


@router.get(
    "/retrospectives/{retrospective_id}",
    response_model=ProjectRetrospective,
)
def get_retrospective(
    retrospective_id: str, current_user: str = Depends(require_auth)
):
    return _get_or_404(retrospective_id)


@router.patch(
    "/retrospectives/{retrospective_id}",
    response_model=ProjectRetrospective,
)
def patch_retrospective(
    retrospective_id: str,
    body: ProjectRetrospectiveUpdate,
    current_user: str = Depends(require_auth),
):
    retro = _get_or_404(retrospective_id)
    updated = update_retrospective(project_retrospective_repo, retro, body)
    audit_writer.write(
        action="project_retrospective_updated",
        target_type="project_retrospective",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"status": updated.status},
    )
    return updated


@router.post(
    "/retrospectives/{retrospective_id}/archive",
    response_model=ProjectRetrospective,
)
def archive(
    retrospective_id: str, current_user: str = Depends(require_auth)
):
    retro = _get_or_404(retrospective_id)
    archived = archive_retrospective(project_retrospective_repo, retro)
    audit_writer.write(
        action="project_retrospective_archived",
        target_type="project_retrospective",
        target_id=archived.id,
        project_id=archived.project_id,
        actor_email=current_user,
    )
    return archived


@router.post(
    "/build-trials/{trial_id}/retrospective/generate",
    response_model=ProjectRetrospective,
    status_code=201,
)
def generate_retrospective_for_trial(
    trial_id: str,
    body: ProjectRetrospectiveGenerateRequest,
    provider_name: str | None = None,
    expensive_approved: bool = False,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    provider, _route_decision = resolve_routed_provider_or_400(
        "analysis",
        provider_name,
        project_id=trial.project_id,
        source_type="build_trial",
        source_id=trial.id,
        expensive_approved=expensive_approved,
    )

    title = body.title or f"Retrospective for trial {trial.name}"
    retro, _artifact = generate_retrospective(
        project_retrospective_repo,
        artifact_repo,
        provider,
        project_id=trial.project_id,
        trial_id=trial.id,
        title=title,
        summary_inputs=body.summary_inputs,
    )
    audit_writer.write(
        action="project_retrospective_generated",
        target_type="project_retrospective",
        target_id=retro.id,
        project_id=retro.project_id,
        actor_email=current_user,
        details={
            "trial_id": trial.id,
            "status": retro.status,
            "provider": retro.provider,
            "model": retro.model,
        },
    )
    return retro


@router.post(
    "/retrospectives/{retrospective_id}/improvement-proposals",
    response_model=ImprovementProposal,
    status_code=201,
)
def create_proposal_from_retrospective(
    retrospective_id: str,
    body: ImprovementProposalCreate,
    current_user: str = Depends(require_auth),
):
    retro = _get_or_404(retrospective_id)
    payload = body.model_copy(
        update={
            "source_type": "retrospective",
            "source_id": retrospective_id,
            "project_id": body.project_id or retro.project_id,
        }
    )
    proposal = create_proposal(improvement_proposal_repo, body=payload)
    # Link proposal back to the retrospective
    updated_proposal_ids = list(retro.proposal_ids)
    if proposal.id not in updated_proposal_ids:
        updated_proposal_ids.append(proposal.id)
        update_retrospective(
            project_retrospective_repo,
            retro,
            ProjectRetrospectiveUpdate(proposal_ids=updated_proposal_ids),
        )
    audit_writer.write(
        action="improvement_proposal_created",
        target_type="improvement_proposal",
        target_id=proposal.id,
        project_id=proposal.project_id,
        actor_email=current_user,
        details={"source_type": "retrospective", "source_id": retrospective_id},
    )
    return proposal
