from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ProjectBuildTrial,
    ProjectBuildTrialComplete,
    ProjectBuildTrialCreate,
    ProjectBuildTrialStage,
    ProjectBuildTrialStageCreate,
    ProjectBuildTrialStageUpdate,
    ProjectBuildTrialSummary,
    ProjectBuildTrialUpdate,
)
from ..repositories_state import (
    project_build_trial_repo,
    project_build_trial_stage_repo,
    project_repo,
)
from ..services.evaluation_trials import (
    add_stage,
    build_summary,
    complete_trial,
    create_trial,
    update_stage,
    update_trial,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/build-trials",
    response_model=ProjectBuildTrial,
    status_code=201,
)
def create_build_trial(
    project_id: str,
    body: ProjectBuildTrialCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return create_trial(project_build_trial_repo, project_id=project_id, body=body)


@router.get(
    "/projects/{project_id}/build-trials",
    response_model=list[ProjectBuildTrial],
)
def list_build_trials(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_build_trial_repo.list_by_project(project_id)


@router.get("/build-trials/{trial_id}", response_model=ProjectBuildTrialSummary)
def get_build_trial(
    trial_id: str,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    stages = project_build_trial_stage_repo.list_by_trial(trial_id)
    return build_summary(trial, stages)


@router.patch("/build-trials/{trial_id}", response_model=ProjectBuildTrial)
def update_build_trial(
    trial_id: str,
    body: ProjectBuildTrialUpdate,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    return update_trial(project_build_trial_repo, trial, body)


@router.post(
    "/build-trials/{trial_id}/stages",
    response_model=ProjectBuildTrialStage,
    status_code=201,
)
def add_build_trial_stage(
    trial_id: str,
    body: ProjectBuildTrialStageCreate,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    return add_stage(
        project_build_trial_stage_repo,
        project_id=trial.project_id,
        trial_id=trial_id,
        body=body,
    )


@router.get(
    "/build-trials/{trial_id}/stages",
    response_model=list[ProjectBuildTrialStage],
)
def list_build_trial_stages(
    trial_id: str,
    current_user: str = Depends(require_auth),
):
    if project_build_trial_repo.get(trial_id) is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    return project_build_trial_stage_repo.list_by_trial(trial_id)


@router.patch(
    "/build-trial-stages/{stage_id}",
    response_model=ProjectBuildTrialStage,
)
def update_build_trial_stage(
    stage_id: str,
    body: ProjectBuildTrialStageUpdate,
    current_user: str = Depends(require_auth),
):
    stage = project_build_trial_stage_repo.get(stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Build trial stage not found")
    return update_stage(project_build_trial_stage_repo, stage, body)


@router.post(
    "/build-trials/{trial_id}/complete",
    response_model=ProjectBuildTrial,
)
def complete_build_trial(
    trial_id: str,
    body: ProjectBuildTrialComplete,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    return complete_trial(
        project_build_trial_repo,
        trial,
        verdict=body.verdict,
        summary=body.summary,
        lessons_learned=body.lessons_learned,
    )
