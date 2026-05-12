from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ExperimentPlan,
    ExperimentPlanCreate,
    ExperimentPlanUpdate,
    ExperimentRun,
    ExperimentRunComplete,
    ExperimentRunCreate,
    ExperimentRunUpdate,
)
from ..repositories_state import (
    audit_writer,
    experiment_plan_repo,
    experiment_run_repo,
    improvement_proposal_repo,
    project_repo,
)
from ..services.experiments import (
    InvalidExperimentTransition,
    approve_plan,
    complete_run,
    create_plan,
    create_run,
    reject_plan,
    update_plan,
    update_run,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _get_plan_or_404(plan_id: str) -> ExperimentPlan:
    plan = experiment_plan_repo.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Experiment plan not found")
    return plan


def _get_run_or_404(run_id: str) -> ExperimentRun:
    run = experiment_run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Experiment run not found")
    return run


@router.post(
    "/experiment-plans",
    response_model=ExperimentPlan,
    status_code=201,
)
def create_experiment_plan(
    body: ExperimentPlanCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    if body.proposal_id is not None:
        if improvement_proposal_repo.get(body.proposal_id) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown proposal_id: {body.proposal_id}",
            )
    plan = create_plan(experiment_plan_repo, body=body)
    audit_writer.write(
        action="experiment_plan_created",
        target_type="experiment_plan",
        target_id=plan.id,
        project_id=plan.project_id,
        actor_email=current_user,
        details={"proposal_id": plan.proposal_id},
    )
    return plan


@router.get("/experiment-plans", response_model=list[ExperimentPlan])
def list_experiment_plans(
    project_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    if proposal_id is not None:
        items = experiment_plan_repo.list_by_proposal(proposal_id)
    elif project_id is not None:
        _ensure_project(project_id)
        items = experiment_plan_repo.list_by_project(project_id)
    else:
        items = experiment_plan_repo.list_all()
    if status is not None:
        items = [p for p in items if p.status == status]
    return items


@router.get(
    "/projects/{project_id}/experiment-plans",
    response_model=list[ExperimentPlan],
)
def list_experiment_plans_for_project(
    project_id: str,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = experiment_plan_repo.list_by_project(project_id)
    if status is not None:
        items = [p for p in items if p.status == status]
    return items


@router.get("/experiment-plans/{plan_id}", response_model=ExperimentPlan)
def get_experiment_plan(
    plan_id: str, current_user: str = Depends(require_auth)
):
    return _get_plan_or_404(plan_id)


@router.patch("/experiment-plans/{plan_id}", response_model=ExperimentPlan)
def patch_experiment_plan(
    plan_id: str,
    body: ExperimentPlanUpdate,
    current_user: str = Depends(require_auth),
):
    plan = _get_plan_or_404(plan_id)
    updated = update_plan(experiment_plan_repo, plan, body)
    audit_writer.write(
        action="experiment_plan_updated",
        target_type="experiment_plan",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


def _try_plan(fn, plan: ExperimentPlan):
    try:
        return fn(experiment_plan_repo, plan)
    except InvalidExperimentTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/experiment-plans/{plan_id}/approve",
    response_model=ExperimentPlan,
)
def approve(plan_id: str, current_user: str = Depends(require_auth)):
    plan = _get_plan_or_404(plan_id)
    updated = _try_plan(approve_plan, plan)
    audit_writer.write(
        action="experiment_plan_approved",
        target_type="experiment_plan",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/experiment-plans/{plan_id}/reject",
    response_model=ExperimentPlan,
)
def reject(plan_id: str, current_user: str = Depends(require_auth)):
    plan = _get_plan_or_404(plan_id)
    updated = _try_plan(reject_plan, plan)
    audit_writer.write(
        action="experiment_plan_rejected",
        target_type="experiment_plan",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


# -- runs -----------------------------------------------------------------


@router.post(
    "/experiment-plans/{plan_id}/runs",
    response_model=ExperimentRun,
    status_code=201,
)
def create_experiment_run(
    plan_id: str,
    body: ExperimentRunCreate,
    current_user: str = Depends(require_auth),
):
    plan = _get_plan_or_404(plan_id)
    run = create_run(experiment_run_repo, plan=plan, body=body)
    audit_writer.write(
        action="experiment_run_created",
        target_type="experiment_run",
        target_id=run.id,
        project_id=run.project_id,
        actor_email=current_user,
        details={"experiment_plan_id": plan.id},
    )
    return run


@router.get(
    "/experiment-plans/{plan_id}/runs",
    response_model=list[ExperimentRun],
)
def list_runs_for_plan(
    plan_id: str, current_user: str = Depends(require_auth)
):
    _get_plan_or_404(plan_id)
    return experiment_run_repo.list_by_plan(plan_id)


@router.get("/experiment-runs/{run_id}", response_model=ExperimentRun)
def get_experiment_run(
    run_id: str, current_user: str = Depends(require_auth)
):
    return _get_run_or_404(run_id)


@router.patch("/experiment-runs/{run_id}", response_model=ExperimentRun)
def patch_experiment_run(
    run_id: str,
    body: ExperimentRunUpdate,
    current_user: str = Depends(require_auth),
):
    run = _get_run_or_404(run_id)
    updated = update_run(experiment_run_repo, run, body)
    audit_writer.write(
        action="experiment_run_updated",
        target_type="experiment_run",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/experiment-runs/{run_id}/complete",
    response_model=ExperimentRun,
)
def complete(
    run_id: str,
    body: ExperimentRunComplete,
    current_user: str = Depends(require_auth),
):
    run = _get_run_or_404(run_id)
    updated = complete_run(experiment_run_repo, run, body)
    audit_writer.write(
        action="experiment_run_completed",
        target_type="experiment_run",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"decision": updated.decision},
    )
    return updated
