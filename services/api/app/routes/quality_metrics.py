from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import QualityMetricSnapshot, QualityMetricsResponse
from ..repositories_state import (
    check_run_repo,
    command_run_repo,
    memory_candidate_repo,
    pr_draft_repo,
    pr_review_repo,
    project_build_trial_repo,
    project_build_trial_stage_repo,
    project_repo,
    quality_metric_snapshot_repo,
    review_feedback_repo,
    tool_run_repo,
)
from ..services.quality_metrics import (
    calculate_project_metrics,
    calculate_trial_metrics,
    create_snapshot,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/quality-metrics",
    response_model=QualityMetricsResponse,
)
def get_project_quality_metrics(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    metrics = calculate_project_metrics(
        project_id=project_id,
        check_run_repo=check_run_repo,
        command_run_repo=command_run_repo,
        tool_run_repo=tool_run_repo,
        pr_review_repo=pr_review_repo,
        review_feedback_repo=review_feedback_repo,
        memory_candidate_repo=memory_candidate_repo,
        project_build_trial_repo=project_build_trial_repo,
        project_build_trial_stage_repo=project_build_trial_stage_repo,
        pr_draft_repo=pr_draft_repo,
    )
    return QualityMetricsResponse(project_id=project_id, metrics=metrics)


@router.get(
    "/build-trials/{trial_id}/quality-metrics",
    response_model=QualityMetricsResponse,
)
def get_trial_quality_metrics(
    trial_id: str,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    metrics = calculate_trial_metrics(
        trial=trial,
        check_run_repo=check_run_repo,
        command_run_repo=command_run_repo,
        tool_run_repo=tool_run_repo,
        review_feedback_repo=review_feedback_repo,
        project_build_trial_stage_repo=project_build_trial_stage_repo,
    )
    return QualityMetricsResponse(
        project_id=trial.project_id,
        trial_id=trial_id,
        metrics=metrics,
    )


@router.post(
    "/build-trials/{trial_id}/quality-metrics/snapshot",
    response_model=QualityMetricSnapshot,
    status_code=201,
)
def snapshot_trial_quality_metrics(
    trial_id: str,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    metrics = calculate_trial_metrics(
        trial=trial,
        check_run_repo=check_run_repo,
        command_run_repo=command_run_repo,
        tool_run_repo=tool_run_repo,
        review_feedback_repo=review_feedback_repo,
        project_build_trial_stage_repo=project_build_trial_stage_repo,
    )
    return create_snapshot(
        quality_metric_snapshot_repo,
        project_id=trial.project_id,
        trial_id=trial_id,
        source_type="build_trial",
        source_id=trial_id,
        metrics=metrics,
    )
