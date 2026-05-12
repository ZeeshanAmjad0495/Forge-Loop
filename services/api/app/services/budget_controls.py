"""Budget controls (Release 9, Task 53).

Sums local CostRecords for a project against a configured BudgetPolicy and
returns advisory/blocking status. No billing API calls. No charges. Local
records only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import BudgetPeriod, BudgetPolicy, BudgetStatus, BudgetStatusValue
from ..repositories import BudgetPolicyRepository, CostRecordRepository


def _period_start(now: datetime, period: BudgetPeriod) -> datetime | None:
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight - timedelta(days=midnight.weekday())
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == "project_lifetime":
        return None
    return None


def _select_policy(
    policies: list[BudgetPolicy],
    *,
    workflow_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> BudgetPolicy | None:
    """Return the most specific enabled policy applicable to the request.

    Specificity: matching workflow > matching provider > project-wide.
    """
    enabled = [p for p in policies if p.enabled]
    if not enabled:
        return None

    def _score(p: BudgetPolicy) -> int:
        s = 0
        if p.workflow_type and workflow_type and p.workflow_type == workflow_type:
            s += 4
        if p.provider and provider and p.provider == provider:
            s += 2
        if p.model and model and p.model == model:
            s += 1
        if not p.workflow_type and not p.provider and not p.model:
            s += 0  # project-wide fallback
        return s

    matches = [p for p in enabled if _is_match(p, workflow_type, provider, model)]
    if not matches:
        return None
    return max(matches, key=_score)


def _is_match(
    policy: BudgetPolicy,
    workflow_type: str | None,
    provider: str | None,
    model: str | None,
) -> bool:
    if policy.workflow_type and policy.workflow_type != workflow_type:
        return False
    if policy.provider and policy.provider != provider:
        return False
    if policy.model and policy.model != model:
        return False
    return True


def _sum_spent(
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    period_start: datetime | None,
    workflow_type: str | None,
    provider: str | None,
    model: str | None,
) -> float:
    records = cost_record_repo.list_by_project(project_id)
    total = 0.0
    for r in records:
        if period_start is not None and r.created_at < period_start:
            continue
        if workflow_type and r.workflow_type != workflow_type:
            continue
        if provider and r.provider != provider:
            continue
        if model and r.model != model:
            continue
        total += float(r.estimated_total_cost_usd or 0.0)
    return total


def get_budget_status(
    budget_policy_repo: BudgetPolicyRepository,
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    workflow_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    estimated_cost_usd: float = 0.0,
) -> BudgetStatus:
    policies = budget_policy_repo.list_by_project(project_id)
    policy = _select_policy(
        policies, workflow_type=workflow_type, provider=provider, model=model
    )
    if policy is None:
        return BudgetStatus(
            project_id=project_id,
            period="project_lifetime",
            spent_usd=0.0,
            status="no_policy",
        )

    now = datetime.now(timezone.utc)
    start = _period_start(now, policy.period)
    spent = _sum_spent(
        cost_record_repo,
        project_id=project_id,
        period_start=start,
        workflow_type=policy.workflow_type,
        provider=policy.provider,
        model=policy.model,
    )

    warnings: list[str] = []
    blocking: list[str] = []
    status: BudgetStatusValue = "ok"

    prospective = spent + max(0.0, float(estimated_cost_usd))

    if policy.per_run_limit_usd is not None and estimated_cost_usd > policy.per_run_limit_usd:
        blocking.append(
            f"estimated_run_cost_{estimated_cost_usd}_exceeds_per_run_limit_{policy.per_run_limit_usd}"
        )
        status = "blocked"

    if policy.hard_limit_usd is not None and prospective >= policy.hard_limit_usd:
        blocking.append(
            f"projected_spend_{prospective}_meets_or_exceeds_hard_limit_{policy.hard_limit_usd}"
        )
        status = "blocked"

    if (
        status != "blocked"
        and policy.warning_limit_usd is not None
        and prospective >= policy.warning_limit_usd
    ):
        warnings.append(
            f"projected_spend_{prospective}_meets_or_exceeds_warning_limit_{policy.warning_limit_usd}"
        )
        status = "warning"

    remaining: float | None = None
    if policy.hard_limit_usd is not None:
        remaining = round(policy.hard_limit_usd - spent, 6)

    return BudgetStatus(
        project_id=project_id,
        period=policy.period,
        spent_usd=round(spent, 6),
        warning_limit_usd=policy.warning_limit_usd,
        hard_limit_usd=policy.hard_limit_usd,
        remaining_usd=remaining,
        status=status,
        warnings=warnings,
        blocking_errors=blocking,
    )


def ensure_budget_allows(
    budget_policy_repo: BudgetPolicyRepository,
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    workflow_type: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    estimated_cost_usd: float = 0.0,
) -> tuple[bool, BudgetStatus]:
    """Return (allowed, status). Helper for callers that want to gate work."""
    status = get_budget_status(
        budget_policy_repo,
        cost_record_repo,
        project_id=project_id,
        workflow_type=workflow_type,
        provider=provider,
        model=model,
        estimated_cost_usd=estimated_cost_usd,
    )
    allowed = status.status != "blocked"
    return allowed, status
