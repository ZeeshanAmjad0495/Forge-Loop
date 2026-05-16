"""Task 83: advisory-only auto-remediation routes.

Findings -> RemediationProposal draft. A DevTask is created only via the
explicit human-approved `/approve` endpoint. No merge/deploy/branch/PR.
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import RemediationProposal
from ..repositories_state import project_repo, remediation_proposal_repo
from ..services import auto_remediation

router = APIRouter()


@router.post(
    "/ci-analyses/{ci_analysis_id}/propose-remediation",
    response_model=RemediationProposal,
    status_code=201,
)
def propose_ci_remediation(
    ci_analysis_id: str, current_user: str = Depends(require_auth)
):
    return auto_remediation.propose_from_ci_analysis(
        ci_analysis_id, current_user
    )


@router.post(
    "/incident-analyses/{incident_analysis_id}/propose-remediation",
    response_model=RemediationProposal,
    status_code=201,
)
def propose_incident_remediation(
    incident_analysis_id: str, current_user: str = Depends(require_auth)
):
    return auto_remediation.propose_from_incident_analysis(
        incident_analysis_id, current_user
    )


@router.post(
    "/pr-reviews/{review_id}/propose-remediation",
    response_model=RemediationProposal,
    status_code=201,
)
def propose_pr_remediation(
    review_id: str, current_user: str = Depends(require_auth)
):
    return auto_remediation.propose_from_pr_review(review_id, current_user)


@router.post(
    "/remediation-proposals/{proposal_id}/approve",
    response_model=RemediationProposal,
)
def approve_remediation(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    return auto_remediation.approve_proposal(proposal_id, current_user)


@router.post(
    "/remediation-proposals/{proposal_id}/reject",
    response_model=RemediationProposal,
)
def reject_remediation(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    return auto_remediation.reject_proposal(proposal_id, current_user)


@router.get(
    "/remediation-proposals/{proposal_id}",
    response_model=RemediationProposal,
)
def get_remediation_proposal(
    proposal_id: str, current_user: str = Depends(require_auth)
):
    p = remediation_proposal_repo.get(proposal_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail="remediation proposal not found"
        )
    return p


@router.get(
    "/projects/{project_id}/remediation-proposals",
    response_model=list[RemediationProposal],
)
def list_remediation_proposals(
    project_id: str, current_user: str = Depends(require_auth)
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return remediation_proposal_repo.list_by_project(project_id)
