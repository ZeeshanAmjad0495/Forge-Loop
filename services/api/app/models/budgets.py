from datetime import datetime
from typing import Literal

from pydantic import BaseModel

BudgetPeriod = Literal["daily", "weekly", "monthly", "project_lifetime"]
BudgetStatusValue = Literal["ok", "warning", "blocked", "no_policy"]


class BudgetPolicyCreate(BaseModel):
    name: str
    enabled: bool = True
    currency: str = "USD"
    period: BudgetPeriod = "monthly"
    warning_limit_usd: float | None = None
    hard_limit_usd: float | None = None
    per_run_limit_usd: float | None = None
    workflow_type: str | None = None
    provider: str | None = None
    model: str | None = None


class BudgetPolicyUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    currency: str | None = None
    period: BudgetPeriod | None = None
    warning_limit_usd: float | None = None
    hard_limit_usd: float | None = None
    per_run_limit_usd: float | None = None
    workflow_type: str | None = None
    provider: str | None = None
    model: str | None = None


class BudgetPolicy(BaseModel):
    id: str
    project_id: str
    name: str
    enabled: bool = True
    currency: str = "USD"
    period: BudgetPeriod = "monthly"
    warning_limit_usd: float | None = None
    hard_limit_usd: float | None = None
    per_run_limit_usd: float | None = None
    workflow_type: str | None = None
    provider: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class BudgetStatus(BaseModel):
    project_id: str
    period: BudgetPeriod
    spent_usd: float
    warning_limit_usd: float | None = None
    hard_limit_usd: float | None = None
    remaining_usd: float | None = None
    status: BudgetStatusValue
    warnings: list[str] = []
    blocking_errors: list[str] = []


class BudgetCheckRequest(BaseModel):
    workflow_type: str | None = None
    estimated_cost_usd: float = 0.0
    provider: str | None = None
    model: str | None = None
