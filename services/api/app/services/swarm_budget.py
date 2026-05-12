"""Swarm budget control (Release 9, Task 56).

Policy and budget gate for *future* multi-agent swarms. ForgeLoop does not
run swarms yet; this layer prevents uncontrolled cost/complexity when it
eventually does. Combines SwarmPolicy with the project BudgetPolicy.
"""

from __future__ import annotations

from ..models import (
    SwarmBudgetCheckRequest,
    SwarmBudgetCheckResponse,
    SwarmPolicy,
)
from ..repositories import (
    BudgetPolicyRepository,
    CostRecordRepository,
    SwarmPolicyRepository,
)
from .budget_controls import get_budget_status


def _select_swarm_policy(
    policies: list[SwarmPolicy], swarm_type: str
) -> SwarmPolicy | None:
    enabled = [p for p in policies if p.enabled]
    if not enabled:
        return None
    # Prefer an exact swarm_type match; fall back to a "custom" / wildcard.
    typed = [p for p in enabled if p.swarm_type == swarm_type]
    if typed:
        return typed[0]
    wildcard = [p for p in enabled if p.swarm_type == "custom"]
    if wildcard:
        return wildcard[0]
    return None


def check_swarm_budget(
    swarm_policy_repo: SwarmPolicyRepository,
    budget_policy_repo: BudgetPolicyRepository,
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    request: SwarmBudgetCheckRequest,
) -> SwarmBudgetCheckResponse:
    policies = swarm_policy_repo.list_by_project(project_id)
    policy = _select_swarm_policy(policies, request.swarm_type)

    warnings: list[str] = []
    blocking: list[str] = []

    if policy is None:
        # No swarm policy → block by default, since swarms aren't sanctioned yet.
        blocking.append("no_swarm_policy_defined_for_project")
        return SwarmBudgetCheckResponse(
            allowed=False,
            warnings=warnings,
            blocking_errors=blocking,
            requires_approval=True,
        )

    if request.requested_agents > policy.max_agents:
        blocking.append(
            f"requested_agents_{request.requested_agents}_exceeds_max_{policy.max_agents}"
        )

    if (
        policy.max_estimated_cost_usd is not None
        and request.estimated_cost_usd > policy.max_estimated_cost_usd
    ):
        blocking.append(
            f"estimated_cost_{request.estimated_cost_usd}_exceeds_swarm_max_{policy.max_estimated_cost_usd}"
        )

    if (
        policy.max_context_tokens_per_agent is not None
        and request.estimated_context_tokens_per_agent
        > policy.max_context_tokens_per_agent
    ):
        warnings.append(
            f"context_tokens_per_agent_{request.estimated_context_tokens_per_agent}_"
            f"exceeds_recommended_{policy.max_context_tokens_per_agent}"
        )

    if policy.allowed_providers:
        not_allowed = [
            p for p in request.providers if p not in policy.allowed_providers
        ]
        if not_allowed:
            blocking.append(
                f"providers_not_allowed_{','.join(sorted(not_allowed))}"
            )

    # Cross-check with project budget if there is an estimated cost.
    if request.estimated_cost_usd > 0:
        budget_status = get_budget_status(
            budget_policy_repo,
            cost_record_repo,
            project_id=project_id,
            estimated_cost_usd=request.estimated_cost_usd,
        )
        if budget_status.status == "blocked":
            blocking.extend(budget_status.blocking_errors)
        elif budget_status.status == "warning":
            warnings.extend(budget_status.warnings)

    allowed = not blocking

    return SwarmBudgetCheckResponse(
        allowed=allowed,
        warnings=warnings,
        blocking_errors=blocking,
        requires_approval=policy.requires_approval,
        policy_id=policy.id,
        policy_name=policy.name,
        max_agents=policy.max_agents,
        max_estimated_cost_usd=policy.max_estimated_cost_usd,
        allowed_providers=list(policy.allowed_providers),
    )
