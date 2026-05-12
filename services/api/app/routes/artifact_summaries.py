from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import ArtifactSummary, ArtifactSummaryCreate
from ..repositories_state import artifact_repo, artifact_summary_repo
from ..services.artifact_summaries import summarize_artifact

router = APIRouter()


@router.post(
    "/artifacts/{artifact_id}/summaries",
    response_model=ArtifactSummary,
    status_code=201,
)
def create_artifact_summary(
    artifact_id: str,
    body: ArtifactSummaryCreate,
    current_user: str = Depends(require_auth),
):
    artifact = artifact_repo.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return summarize_artifact(
        artifact_summary_repo,
        artifact,
        summary_type=body.summary_type,
        provider=body.provider,
        model=body.model,
    )


@router.get(
    "/artifacts/{artifact_id}/summaries",
    response_model=list[ArtifactSummary],
)
def list_artifact_summaries(
    artifact_id: str,
    current_user: str = Depends(require_auth),
):
    if artifact_repo.get(artifact_id) is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact_summary_repo.list_by_artifact(artifact_id)


@router.get(
    "/artifact-summaries/{summary_id}",
    response_model=ArtifactSummary,
)
def get_artifact_summary(
    summary_id: str,
    current_user: str = Depends(require_auth),
):
    summary = artifact_summary_repo.get(summary_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Artifact summary not found")
    return summary
