import uuid
from datetime import datetime, timezone

from app.models import BudgetPolicy
from app.repositories import (
    InMemoryBudgetPolicyRepository,
    InMemoryCostRecordRepository,
)
from app.services.budget_controls import ensure_budget_allows, get_budget_status
from app.services.cost_tracking import record_cost


def _policy(
    project_id: str = "p1",
    name: str = "P",
    period: str = "monthly",
    warning_limit_usd: float | None = None,
    hard_limit_usd: float | None = None,
    per_run_limit_usd: float | None = None,
    workflow_type: str | None = None,
    provider: str | None = None,
    enabled: bool = True,
) -> BudgetPolicy:
    now = datetime.now(timezone.utc)
    return BudgetPolicy(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=name,
        period=period,  # type: ignore[arg-type]
        warning_limit_usd=warning_limit_usd,
        hard_limit_usd=hard_limit_usd,
        per_run_limit_usd=per_run_limit_usd,
        workflow_type=workflow_type,
        provider=provider,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


def _spend(cost_repo, project_id: str, cost: float, workflow_type: str = "analysis"):
    return record_cost(
        cost_repo,
        project_id=project_id,
        source_type="agent_run",
        source_id="s",
        workflow_type=workflow_type,  # type: ignore[arg-type]
        provider="deepseek",
        model="d",
        estimated_input_cost_usd=cost,
    )


def test_budget_status_no_policy():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    status = get_budget_status(
        budget_repo, cost_repo, project_id="p1"
    )
    assert status.status == "no_policy"


def test_budget_status_ok_under_warning():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(warning_limit_usd=10.0, hard_limit_usd=100.0))
    _spend(cost_repo, "p1", 1.0)
    status = get_budget_status(budget_repo, cost_repo, project_id="p1")
    assert status.status == "ok"
    assert status.spent_usd == 1.0


def test_budget_status_warning_threshold():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(warning_limit_usd=5.0, hard_limit_usd=100.0))
    _spend(cost_repo, "p1", 5.0)
    status = get_budget_status(budget_repo, cost_repo, project_id="p1")
    assert status.status == "warning"
    assert status.warnings


def test_budget_status_hard_limit_blocks():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(warning_limit_usd=5.0, hard_limit_usd=10.0))
    _spend(cost_repo, "p1", 10.0)
    status = get_budget_status(budget_repo, cost_repo, project_id="p1")
    assert status.status == "blocked"
    assert status.blocking_errors


def test_budget_per_run_limit_blocks():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(
        _policy(warning_limit_usd=10.0, hard_limit_usd=100.0, per_run_limit_usd=1.0)
    )
    status = get_budget_status(
        budget_repo, cost_repo, project_id="p1", estimated_cost_usd=2.0
    )
    assert status.status == "blocked"
    assert any("per_run_limit" in m for m in status.blocking_errors)


def test_policy_specificity_workflow_match_wins():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(name="global", hard_limit_usd=100.0))
    budget_repo.save(
        _policy(name="wf", workflow_type="analysis", hard_limit_usd=5.0)
    )
    _spend(cost_repo, "p1", 5.0, workflow_type="analysis")
    status = get_budget_status(
        budget_repo, cost_repo, project_id="p1", workflow_type="analysis"
    )
    assert status.status == "blocked"
    assert status.hard_limit_usd == 5.0


def test_disabled_policy_is_ignored():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(warning_limit_usd=1.0, hard_limit_usd=1.0, enabled=False))
    _spend(cost_repo, "p1", 5.0)
    status = get_budget_status(budget_repo, cost_repo, project_id="p1")
    assert status.status == "no_policy"


def test_ensure_budget_allows_returns_pair():
    budget_repo = InMemoryBudgetPolicyRepository()
    cost_repo = InMemoryCostRecordRepository()
    budget_repo.save(_policy(hard_limit_usd=10.0))
    _spend(cost_repo, "p1", 9.0)
    allowed, status = ensure_budget_allows(
        budget_repo,
        cost_repo,
        project_id="p1",
        estimated_cost_usd=2.0,
    )
    assert allowed is False
    assert status.status == "blocked"


# -- API tests --------------------------------------------------------------


def test_create_and_list_budget_policies(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/budget-policies",
        json={"name": "monthly", "hard_limit_usd": 10.0, "warning_limit_usd": 5.0},
    )
    assert res.status_code == 201
    created = res.json()
    assert created["project_id"] == project_id

    listed = client.get(f"/projects/{project_id}/budget-policies").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_update_budget_policy(client, project):
    project_id = project["id"]
    created = client.post(
        f"/projects/{project_id}/budget-policies",
        json={"name": "monthly", "hard_limit_usd": 10.0},
    ).json()
    res = client.patch(
        f"/budget-policies/{created['id']}",
        json={"hard_limit_usd": 25.0, "enabled": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["hard_limit_usd"] == 25.0
    assert body["enabled"] is False


def test_budget_status_endpoint_no_policy(client, project):
    project_id = project["id"]
    res = client.get(f"/projects/{project_id}/budget-status")
    assert res.status_code == 200
    assert res.json()["status"] == "no_policy"


def test_budget_check_endpoint_blocks_per_run(client, project):
    project_id = project["id"]
    client.post(
        f"/projects/{project_id}/budget-policies",
        json={
            "name": "monthly",
            "hard_limit_usd": 100.0,
            "per_run_limit_usd": 0.5,
        },
    )
    res = client.post(
        f"/projects/{project_id}/budget-check",
        json={"estimated_cost_usd": 1.0},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "blocked"


def test_budget_policy_unknown_project(client):
    res = client.post(
        "/projects/missing/budget-policies",
        json={"name": "x"},
    )
    assert res.status_code == 404
