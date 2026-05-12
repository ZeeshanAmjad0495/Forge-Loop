import uuid
from datetime import datetime, timezone

from app.models import BudgetPolicy, SwarmBudgetCheckRequest, SwarmPolicy
from app.repositories import (
    InMemoryBudgetPolicyRepository,
    InMemoryCostRecordRepository,
    InMemorySwarmPolicyRepository,
)
from app.services.swarm_budget import check_swarm_budget


def _swarm(
    project_id: str = "p1",
    swarm_type: str = "pr_review",
    max_agents: int = 3,
    max_estimated_cost_usd: float | None = None,
    allowed_providers: list[str] | None = None,
    requires_approval: bool = True,
    enabled: bool = True,
) -> SwarmPolicy:
    now = datetime.now(timezone.utc)
    return SwarmPolicy(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="p",
        swarm_type=swarm_type,  # type: ignore[arg-type]
        max_agents=max_agents,
        max_estimated_cost_usd=max_estimated_cost_usd,
        allowed_providers=list(allowed_providers or []),
        requires_approval=requires_approval,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


def test_no_swarm_policy_blocks():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(swarm_type="pr_review", requested_agents=2),
    )
    assert res.allowed is False
    assert "no_swarm_policy_defined_for_project" in res.blocking_errors


def test_request_under_limits_allowed():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(max_agents=3))
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(swarm_type="pr_review", requested_agents=2),
    )
    assert res.allowed is True
    assert res.requires_approval is True
    assert res.max_agents == 3


def test_request_over_max_agents_blocked():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(max_agents=3))
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(swarm_type="pr_review", requested_agents=5),
    )
    assert res.allowed is False
    assert any("exceeds_max_3" in b for b in res.blocking_errors)


def test_request_over_estimated_cost_blocked():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(max_estimated_cost_usd=0.5))
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(
            swarm_type="pr_review", requested_agents=2, estimated_cost_usd=1.0
        ),
    )
    assert res.allowed is False
    assert any("exceeds_swarm_max" in b for b in res.blocking_errors)


def test_disallowed_provider_blocked():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(allowed_providers=["ollama", "deepseek"]))
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(
            swarm_type="pr_review", requested_agents=2, providers=["openai"]
        ),
    )
    assert res.allowed is False
    assert any("providers_not_allowed" in b for b in res.blocking_errors)


def test_custom_swarm_policy_fallback():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(swarm_type="custom", max_agents=4))
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(swarm_type="research", requested_agents=4),
    )
    assert res.allowed is True


def test_project_budget_blocks_swarm():
    swarm_repo = InMemorySwarmPolicyRepository()
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    swarm_repo.save(_swarm(max_estimated_cost_usd=100.0))
    budget_repo.save(
        BudgetPolicy(
            id="bp",
            project_id="p1",
            name="b",
            period="monthly",
            hard_limit_usd=0.5,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    res = check_swarm_budget(
        swarm_repo,
        budget_repo,
        cost_repo,
        project_id="p1",
        request=SwarmBudgetCheckRequest(
            swarm_type="pr_review", requested_agents=2, estimated_cost_usd=1.0
        ),
    )
    assert res.allowed is False
    assert any("hard_limit" in b for b in res.blocking_errors)


# -- API tests --------------------------------------------------------------


def test_create_and_list_swarm_policy(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/swarm-policies",
        json={"name": "pr-review", "swarm_type": "pr_review", "max_agents": 4},
    )
    assert res.status_code == 201
    created = res.json()
    assert created["max_agents"] == 4

    listed = client.get(f"/projects/{project_id}/swarm-policies").json()
    assert len(listed) == 1


def test_update_swarm_policy(client, project):
    project_id = project["id"]
    created = client.post(
        f"/projects/{project_id}/swarm-policies",
        json={"name": "x"},
    ).json()
    res = client.patch(
        f"/swarm-policies/{created['id']}",
        json={"max_agents": 5, "requires_approval": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["max_agents"] == 5
    assert body["requires_approval"] is False


def test_swarm_budget_check_endpoint(client, project):
    project_id = project["id"]
    client.post(
        f"/projects/{project_id}/swarm-policies",
        json={
            "name": "pr",
            "swarm_type": "pr_review",
            "max_agents": 3,
            "allowed_providers": ["deepseek", "ollama"],
        },
    )
    res = client.post(
        f"/projects/{project_id}/swarm-budget-check",
        json={
            "swarm_type": "pr_review",
            "requested_agents": 5,
            "providers": ["openai"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is False
    assert any("exceeds_max" in b for b in body["blocking_errors"])
    assert any("providers_not_allowed" in b for b in body["blocking_errors"])


def test_swarm_policy_unknown_project(client):
    res = client.post(
        "/projects/missing/swarm-policies",
        json={"name": "x"},
    )
    assert res.status_code == 404
