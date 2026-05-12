from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ExperimentPlanStatus = Literal[
    "proposed",
    "approved",
    "running",
    "completed",
    "failed",
    "rejected",
    "archived",
]

ExperimentRunStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]

ExperimentRunDecision = Literal[
    "accept_change",
    "reject_change",
    "inconclusive",
    "needs_more_data",
    "not_decided",
]


class ExperimentPlanCreate(BaseModel):
    title: str
    hypothesis: str = ""
    project_id: str | None = None
    proposal_id: str | None = None
    metric_names: list[str] = []
    baseline_summary: str | None = None
    success_criteria: str = ""
    risk: str = ""


class ExperimentPlanUpdate(BaseModel):
    title: str | None = None
    hypothesis: str | None = None
    proposal_id: str | None = None
    metric_names: list[str] | None = None
    baseline_summary: str | None = None
    success_criteria: str | None = None
    risk: str | None = None


class ExperimentPlan(BaseModel):
    id: str
    project_id: str | None = None
    proposal_id: str | None = None
    title: str
    hypothesis: str = ""
    status: ExperimentPlanStatus = "proposed"
    metric_names: list[str] = []
    baseline_summary: str | None = None
    success_criteria: str = ""
    risk: str = ""
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None


class ExperimentRunCreate(BaseModel):
    baseline_metrics: dict[str, float] = {}
    result_metrics: dict[str, float] = {}
    summary: str | None = None
    status: ExperimentRunStatus = "pending"


class ExperimentRunUpdate(BaseModel):
    status: ExperimentRunStatus | None = None
    baseline_metrics: dict[str, float] | None = None
    result_metrics: dict[str, float] | None = None
    summary: str | None = None
    decision: ExperimentRunDecision | None = None
    artifact_id: str | None = None
    error_message: str | None = None


class ExperimentRunComplete(BaseModel):
    decision: ExperimentRunDecision = "not_decided"
    result_metrics: dict[str, float] = {}
    summary: str | None = None


class ExperimentRun(BaseModel):
    id: str
    project_id: str | None = None
    experiment_plan_id: str
    status: ExperimentRunStatus = "pending"
    baseline_metrics: dict[str, float] = {}
    result_metrics: dict[str, float] = {}
    summary: str | None = None
    decision: ExperimentRunDecision = "not_decided"
    artifact_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
