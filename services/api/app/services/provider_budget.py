"""Task 76: provider budget guard.

Decides whether a provider call is permitted under the daily-USD and
per-task budget policy. Pure logic over CostRecord history — never calls
a provider. The expensive provider (config.EXPENSIVE_PROVIDER, default
kimi) is FAIL-CLOSED: missing approval, exceeded daily budget, exceeded
per-task call cap, or an unexpected computation error -> blocked.

Kept independent of the generic project BudgetPolicy system
(budget_controls.py): that is a per-project spend policy; this is a
provider-cost guard wired at the LLM/routing boundary (Task 76 scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .. import config as _config


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    blocked_reason: str | None = None
    daily_spend_usd: float = 0.0
    daily_budget_usd: float | None = None
    task_call_count: int = 0


def _start_of_utc_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _record_cost_value(r) -> float:
    actual = getattr(r, "actual_cost_usd", None)
    if actual is not None:
        return float(actual)
    return float(getattr(r, "estimated_total_cost_usd", 0.0) or 0.0)


def _daily_spend(repo, project_id: str, provider: str, since: datetime):
    total = 0.0
    for r in repo.list_by_project(project_id):
        if r.provider != provider:
            continue
        if getattr(r, "status", "completed") == "blocked":
            continue
        if r.created_at < since:
            continue
        total += _record_cost_value(r)
    return total


def _task_call_count(
    repo, project_id: str, provider: str, source_id: str, since: datetime
) -> int:
    n = 0
    for r in repo.list_by_project(project_id):
        if (
            r.provider == provider
            and r.source_id == source_id
            and getattr(r, "status", "completed") != "blocked"
            and r.created_at >= since
        ):
            n += 1
    return n


def check_provider_allowed(
    cost_record_repo,
    *,
    project_id: str,
    provider: str,
    source_id: str,
    approval_present: bool = False,
    now: datetime | None = None,
) -> BudgetDecision:
    if not _config.PROVIDER_BUDGETS_ENABLED:
        return BudgetDecision(allowed=True)
    now = now or datetime.now(timezone.utc)
    since = _start_of_utc_day(now)
    expensive = _config.EXPENSIVE_PROVIDER
    try:
        if provider == expensive:
            if _config.KIMI_REQUIRE_APPROVAL and not approval_present:
                return BudgetDecision(
                    False, "expensive_provider_requires_approval"
                )
            spend = _daily_spend(cost_record_repo, project_id, provider, since)
            cap = float(_config.DAILY_KIMI_BUDGET_USD)
            if spend >= cap:
                return BudgetDecision(
                    False, "expensive_daily_budget_exceeded", spend, cap
                )
            calls = _task_call_count(
                cost_record_repo, project_id, provider, source_id, since
            )
            if calls >= int(_config.MAX_KIMI_CALLS_PER_TASK):
                return BudgetDecision(
                    False, "expensive_max_calls_per_task", spend, cap, calls
                )
            return BudgetDecision(True, None, spend, cap, calls)

        if provider == _config.NORMAL_REASONING_PROVIDER:
            spend = _daily_spend(cost_record_repo, project_id, provider, since)
            cap = float(_config.DAILY_DEEPSEEK_BUDGET_USD)
            if spend >= cap:
                return BudgetDecision(
                    False, "normal_provider_daily_budget_exceeded", spend, cap
                )
            return BudgetDecision(True, None, spend, cap)

        return BudgetDecision(allowed=True)
    except Exception:
        if provider == expensive and _config.BUDGET_FAIL_CLOSED_FOR_EXPENSIVE:
            return BudgetDecision(False, "budget_check_failed_fail_closed")
        return BudgetDecision(allowed=True)


def record_blocked(
    cost_record_repo,
    *,
    project_id: str,
    source_type: str,
    source_id: str,
    workflow_type: str,
    provider: str,
    model: str,
    blocked_reason: str,
    was_expensive: bool,
    required_approval: bool,
    approval_id: str | None = None,
):
    """Persist a `blocked` audit CostRecord (zero cost) for traceability."""
    from .cost_tracking import record_cost

    return record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type=source_type,  # type: ignore[arg-type]
        source_id=source_id,
        workflow_type=workflow_type,  # type: ignore[arg-type]
        provider=provider,
        model=model,
        status="blocked",
        selected_provider=provider,
        selected_model=model,
        was_expensive_provider=was_expensive,
        required_approval=required_approval,
        approval_id=approval_id,
        blocked_reason=blocked_reason,
    )


__all__ = ["BudgetDecision", "check_provider_allowed", "record_blocked"]
