from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..repositories_state import (
    cost_record_repo,
    dev_task_repo,
    project_build_trial_repo,
    project_repo,
    requirement_repo,
)
from ..services.cost_reporting import cost_report_for_source, project_cost_report

router = APIRouter()


@router.get("/projects/{project_id}/cost-report")
def get_project_cost_report(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "project_id": project_id,
        **project_cost_report(cost_record_repo, project_id=project_id),
    }


@router.get("/build-trials/{trial_id}/cost-report")
def get_trial_cost_report(
    trial_id: str,
    current_user: str = Depends(require_auth),
):
    trial = project_build_trial_repo.get(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Build trial not found")
    report = cost_report_for_source(
        cost_record_repo,
        project_id=trial.project_id,
        source_type="build_trial",
        source_id=trial_id,
    )
    return {"trial_id": trial_id, "project_id": trial.project_id, **report}


@router.get("/dev-tasks/{dev_task_id}/cost-report")
def get_dev_task_cost_report(
    dev_task_id: str,
    current_user: str = Depends(require_auth),
):
    task = dev_task_repo.get(dev_task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Dev task not found")
    report = cost_report_for_source(
        cost_record_repo,
        project_id=task.project_id,
        source_type="task_decomposition",
        source_id=dev_task_id,
    )
    return {"dev_task_id": dev_task_id, "project_id": task.project_id, **report}


@router.get("/requirements/{requirement_id}/cost-report")
def get_requirement_cost_report(
    requirement_id: str,
    current_user: str = Depends(require_auth),
):
    requirement = requirement_repo.get(requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    report = cost_report_for_source(
        cost_record_repo,
        project_id=requirement.project_id,
        source_type="requirement_analysis",
        source_id=requirement_id,
    )
    return {
        "requirement_id": requirement_id,
        "project_id": requirement.project_id,
        **report,
    }
