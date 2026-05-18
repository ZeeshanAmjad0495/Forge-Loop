"""Task 88 — CostRecord + BudgetGuard wired into routed execution.

The routed-execution chokepoint (resolve_routed_provider) must run the
provider BudgetGuard and persist a planned/blocked CostRecord. No real
providers / keys / network (constructing a provider with a placeholder
key makes no call).
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories import InMemoryCostRecordRepository
from app.services.cost_tracking import record_cost
from app.services.model_routing import resolve_routed_provider

client = TestClient(app)


def _repo():
    return InMemoryCostRecordRepository()


def test_routed_real_provider_persists_planned_cost_record(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    repo = _repo()
    provider, decision = resolve_routed_provider(
        "planning",
        project_id="p1",
        source_id="ticket-1",
        cost_record_repo=repo,
    )
    recs = repo.list_by_project("p1")
    assert len(recs) == 1
    assert recs[0].status == "planned"
    assert recs[0].provider == "deepseek"
    assert recs[0].routing_reason == decision.reason
    assert recs[0].project_id == "p1"


def test_no_cost_record_on_mock_profile(monkeypatch):
    """Mock no-provider profile must not record cost even when a repo is
    supplied (no real provider spend to guard)."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    repo = _repo()
    provider, _ = resolve_routed_provider(
        "planning", project_id="p1", cost_record_repo=repo
    )
    assert provider.provider_name == "mock"
    assert repo.list_by_project("p1") == []


def test_no_cost_record_when_repo_not_supplied(monkeypatch):
    """Task 87 back-compat: omitting cost_record_repo skips persistence."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    provider, _ = resolve_routed_provider("planning", project_id="p1")
    assert provider.provider_name == "mock"


def test_kimi_blocked_by_budget_guard_records_blocked(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "KIMI_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "KIMI_AUTO_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config, "PROVIDER_BUDGETS_ENABLED", True)
    repo = _repo()
    # decide_route selects kimi (override + allow + approved), but the
    # BudgetGuard sees approval_present=False and blocks it.
    provider, decision = resolve_routed_provider(
        "planning",
        provider_override="kimi",
        project_id="p1",
        source_id="t1",
        allow_expensive_provider=True,
        expensive_approved=True,
        approval_present=False,
        cost_record_repo=repo,
    )
    assert provider.provider_name != "kimi"
    assert decision.expensive_provider_blocked is True
    blocked = [r for r in repo.list_by_project("p1") if r.status == "blocked"]
    assert len(blocked) == 1
    assert blocked[0].blocked_reason == "expensive_provider_requires_approval"


def test_deepseek_daily_budget_exceeded_blocks(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "PROVIDER_BUDGETS_ENABLED", True)
    monkeypatch.setattr(config, "DAILY_DEEPSEEK_BUDGET_USD", 1.0)
    repo = _repo()
    record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="seed",
        workflow_type="planning",
        provider="deepseek",
        model="deepseek-v4-flash",
        estimated_input_cost_usd=2.0,
        status="completed",
    )
    _, decision = resolve_routed_provider(
        "planning", project_id="p1", source_id="t2", cost_record_repo=repo
    )
    blocked = [r for r in repo.list_by_project("p1") if r.status == "blocked"]
    assert len(blocked) == 1
    assert blocked[0].blocked_reason == "normal_provider_daily_budget_exceeded"
    assert decision.expensive_provider_blocked is True


def test_planning_route_mock_default_no_cost_record_no_regression():
    """End-to-end: the default mock planning flow still 201s and writes
    no cost record (mock profile)."""
    proj = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    ticket = client.post(
        "/tickets",
        json={"title": "t", "description": "d", "project_id": proj["id"]},
    ).json()
    res = client.post(f"/tickets/{ticket['id']}/planning-runs")
    assert res.status_code == 201
    recs = client.get(f"/projects/{proj['id']}/cost-records")
    assert recs.status_code == 200
    assert recs.json() == []


def test_expensive_approved_body_knob_present():
    """The per-request approval knob is exposed on the planning body."""
    from app.models import PlanningRunCreate

    m = PlanningRunCreate()
    assert m.expensive_approved is False
    m2 = PlanningRunCreate(expensive_approved=True)
    assert m2.expensive_approved is True
