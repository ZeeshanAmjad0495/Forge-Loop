"""Experiment plan/run service (Release 11, Task 68).

Lightweight tracking for proposed-change experiments. The service does NOT
execute experiments, run external commands, or change code. It records
planned experiments and human-supplied metrics/decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    ExperimentPlan,
    ExperimentPlanCreate,
    ExperimentPlanStatus,
    ExperimentPlanUpdate,
    ExperimentRun,
    ExperimentRunComplete,
    ExperimentRunCreate,
    ExperimentRunStatus,
    ExperimentRunUpdate,
)
from ..repositories import ExperimentPlanRepository, ExperimentRunRepository

_PLAN_TRANSITIONS: dict[ExperimentPlanStatus, set[ExperimentPlanStatus]] = {
    "proposed": {"approved", "rejected", "archived"},
    "approved": {"running", "rejected", "archived"},
    "running": {"completed", "failed", "archived"},
    "completed": {"archived"},
    "failed": {"archived"},
    "rejected": {"proposed", "archived"},
    "archived": set(),
}


class InvalidExperimentTransition(ValueError):
    """Raised on unsupported experiment-plan status transitions."""


def _ensure_plan_transition(
    plan: ExperimentPlan, new_status: ExperimentPlanStatus
) -> None:
    if new_status == plan.status:
        return
    if new_status not in _PLAN_TRANSITIONS[plan.status]:
        raise InvalidExperimentTransition(
            f"Cannot transition plan {plan.status!r} -> {new_status!r}"
        )


def create_plan(
    repo: ExperimentPlanRepository,
    *,
    body: ExperimentPlanCreate,
) -> ExperimentPlan:
    now = datetime.now(timezone.utc)
    plan = ExperimentPlan(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        proposal_id=body.proposal_id,
        title=body.title,
        hypothesis=body.hypothesis,
        status="proposed",
        metric_names=list(body.metric_names),
        baseline_summary=body.baseline_summary,
        success_criteria=body.success_criteria,
        risk=body.risk,
        created_at=now,
        updated_at=now,
    )
    repo.save(plan)
    return plan


def update_plan(
    repo: ExperimentPlanRepository,
    plan: ExperimentPlan,
    body: ExperimentPlanUpdate,
) -> ExperimentPlan:
    data = plan.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ExperimentPlan(**data)
    repo.update(updated)
    return updated


def _transition_plan(
    repo: ExperimentPlanRepository,
    plan: ExperimentPlan,
    new_status: ExperimentPlanStatus,
) -> ExperimentPlan:
    _ensure_plan_transition(plan, new_status)
    now = datetime.now(timezone.utc)
    data = plan.model_dump()
    data["status"] = new_status
    data["updated_at"] = now
    if new_status == "approved" and not data.get("approved_at"):
        data["approved_at"] = now
    updated = ExperimentPlan(**data)
    repo.update(updated)
    return updated


def approve_plan(repo, plan):
    return _transition_plan(repo, plan, "approved")


def reject_plan(repo, plan):
    return _transition_plan(repo, plan, "rejected")


# -- runs -----------------------------------------------------------------


def create_run(
    repo: ExperimentRunRepository,
    *,
    plan: ExperimentPlan,
    body: ExperimentRunCreate,
) -> ExperimentRun:
    now = datetime.now(timezone.utc)
    started_at = now if body.status == "running" else None
    completed_at = (
        now if body.status in {"completed", "failed", "cancelled"} else None
    )
    run = ExperimentRun(
        id=str(uuid.uuid4()),
        project_id=plan.project_id,
        experiment_plan_id=plan.id,
        status=body.status,
        baseline_metrics=dict(body.baseline_metrics),
        result_metrics=dict(body.result_metrics),
        summary=body.summary,
        decision="not_decided",
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
    )
    repo.save(run)
    return run


_RUN_RUNNING = {"running"}
_RUN_TERMINAL = {"completed", "failed", "cancelled"}


def update_run(
    repo: ExperimentRunRepository,
    run: ExperimentRun,
    body: ExperimentRunUpdate,
) -> ExperimentRun:
    data = run.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    now = datetime.now(timezone.utc)
    new_status: ExperimentRunStatus | None = data.get("status")
    if new_status in _RUN_RUNNING and run.status not in _RUN_RUNNING and not data.get(
        "started_at"
    ):
        data["started_at"] = now
    if new_status in _RUN_TERMINAL and not data.get("completed_at"):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = ExperimentRun(**data)
    repo.update(updated)
    return updated


def complete_run(
    repo: ExperimentRunRepository,
    run: ExperimentRun,
    body: ExperimentRunComplete,
) -> ExperimentRun:
    now = datetime.now(timezone.utc)
    data = run.model_dump()
    data["status"] = "completed"
    data["decision"] = body.decision
    if body.result_metrics:
        data["result_metrics"] = dict(body.result_metrics)
    if body.summary is not None:
        data["summary"] = body.summary
    data["completed_at"] = now
    data["updated_at"] = now
    updated = ExperimentRun(**data)
    repo.update(updated)
    return updated
