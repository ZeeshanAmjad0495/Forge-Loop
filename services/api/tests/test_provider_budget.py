"""Task 76: provider usage audit records + budget guard.

No real providers / keys. Langfuse stays optional (default no-op)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories import InMemoryCostRecordRepository
from app.services import provider_budget
from app.services.cost_tracking import record_cost

client = TestClient(app)


def _repo():
    return InMemoryCostRecordRepository()


# 1. DeepSeek usage record created for normal reasoning.
def test_deepseek_usage_record_created():
    repo = _repo()
    rec = record_cost(
        repo, project_id="p1", source_type="agent_run", source_id="s1",
        workflow_type="planning", provider="deepseek", model="deepseek-chat",
        input_tokens=100, output_tokens=50,
        estimated_input_cost_usd=0.001, estimated_output_cost_usd=0.002,
        status="completed", routing_reason="default_reasoning_workflow",
        fallback_chain=["deepseek"],
    )
    assert rec.status == "completed"
    assert rec.selected_provider == "deepseek"
    assert rec.routing_reason == "default_reasoning_workflow"
    assert rec.completed_at is not None
    assert repo.list_by_project("p1")[0].id == rec.id


# 2. Ollama usage record with zero estimated external cost.
def test_ollama_usage_record_zero_cost():
    repo = _repo()
    rec = record_cost(
        repo, project_id="p1", source_type="artifact_summary", source_id="s",
        workflow_type="memory", provider="ollama",
        model="qwen2.5-coder:3b", input_tokens=10, output_tokens=5,
    )
    assert rec.provider == "ollama"
    assert rec.estimated_total_cost_usd == 0.0


# 3. Kimi blocked without approval/budget.
def test_kimi_blocked_without_approval():
    d = provider_budget.check_provider_allowed(
        _repo(), project_id="p1", provider="kimi", source_id="t1",
        approval_present=False,
    )
    assert d.allowed is False
    assert d.blocked_reason == "expensive_provider_requires_approval"


# 4. Kimi allowed only when approval present (and within budget).
def test_kimi_allowed_with_approval_and_budget(monkeypatch):
    monkeypatch.setattr(config, "DAILY_KIMI_BUDGET_USD", 1.00)
    monkeypatch.setattr(config, "MAX_KIMI_CALLS_PER_TASK", 3)
    d = provider_budget.check_provider_allowed(
        _repo(), project_id="p1", provider="kimi", source_id="t1",
        approval_present=True,
    )
    assert d.allowed is True
    assert d.blocked_reason is None


# 5. Provider failure records failed status.
def test_failed_status_recorded():
    repo = _repo()
    rec = record_cost(
        repo, project_id="p1", source_type="agent_run", source_id="s",
        workflow_type="planning", provider="deepseek", model="m",
        status="failed", blocked_reason=None,
    )
    assert rec.status == "failed"
    assert rec.completed_at is not None


# 6. Missing Langfuse does not break usage recording.
def test_missing_langfuse_ok(monkeypatch):
    monkeypatch.setattr(config, "LANGFUSE_ENABLED", False)
    from app.services import observability
    observability.reset_observability_provider()
    rec = record_cost(
        _repo(), project_id="p1", source_type="agent_run", source_id="s",
        workflow_type="planning", provider="deepseek", model="m",
    )
    assert rec.id  # persisted without error despite no Langfuse


# 7. Budget limit blocks expensive provider.
def test_daily_budget_blocks_kimi(monkeypatch):
    monkeypatch.setattr(config, "DAILY_KIMI_BUDGET_USD", 0.50)
    repo = _repo()
    # Seed today's kimi spend at the cap.
    record_cost(
        repo, project_id="p1", source_type="agent_run", source_id="prev",
        workflow_type="planning", provider="kimi", model="kimi-k2.6",
        estimated_input_cost_usd=0.40, estimated_output_cost_usd=0.20,
        status="completed",
    )
    d = provider_budget.check_provider_allowed(
        repo, project_id="p1", provider="kimi", source_id="t2",
        approval_present=True,
    )
    assert d.allowed is False
    assert d.blocked_reason == "expensive_daily_budget_exceeded"


def test_per_task_call_cap_blocks_kimi(monkeypatch):
    monkeypatch.setattr(config, "DAILY_KIMI_BUDGET_USD", 100.0)
    monkeypatch.setattr(config, "MAX_KIMI_CALLS_PER_TASK", 2)
    repo = _repo()
    for _ in range(2):
        record_cost(
            repo, project_id="p1", source_type="agent_run",
            source_id="task-X", workflow_type="planning", provider="kimi",
            model="kimi-k2.6", status="completed",
        )
    d = provider_budget.check_provider_allowed(
        repo, project_id="p1", provider="kimi", source_id="task-X",
        approval_present=True,
    )
    assert d.allowed is False
    assert d.blocked_reason == "expensive_max_calls_per_task"


def test_budgets_disabled_allows_all(monkeypatch):
    monkeypatch.setattr(config, "PROVIDER_BUDGETS_ENABLED", False)
    d = provider_budget.check_provider_allowed(
        _repo(), project_id="p1", provider="kimi", source_id="t",
        approval_present=False,
    )
    assert d.allowed is True


# 8a. Kimi override w/o approval is neutralised (Task 75 routing guard)
# and a routing audit record is written.
def test_preview_route_kimi_override_without_approval_neutralised():
    p = client.post(
        "/projects", json={"name": "B76", "description": "d"}
    ).json()
    r = client.post(
        f"/projects/{p['id']}/model-route/preview",
        json={"workflow_type": "planning", "override_provider": "kimi"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["selected_provider"] != "kimi"
    assert d["expensive_provider_blocked"] is True
    costs = client.get(f"/projects/{p['id']}/cost-records").json()
    assert any(c["routing_reason"] for c in costs)  # audit recorded


# 8b. Task 76 budget guard: when routing DOES select Kimi (explicitly
# allowed + approved) but the daily budget is exceeded, the preview
# reroutes to the normal provider and writes a blocked audit record.
def test_preview_route_budget_blocks_kimi_when_over_cap(monkeypatch):
    monkeypatch.setattr(config, "DAILY_KIMI_BUDGET_USD", 0.10)
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    p = client.post(
        "/projects", json={"name": "B76c", "description": "d"}
    ).json()
    from app.repositories_state import cost_record_repo
    record_cost(
        cost_record_repo, project_id=p["id"], source_type="agent_run",
        source_id="prev", workflow_type="planning", provider="kimi",
        model="kimi-k2.6", estimated_input_cost_usd=0.20, status="completed",
    )
    r = client.post(
        f"/projects/{p['id']}/model-route/preview",
        json={
            "workflow_type": "long_context_review",
            "allow_expensive_provider": True,
            "expensive_approved": True,
            "source_id": "task-Y",
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["selected_provider"] != "kimi"
    assert d["expensive_provider_blocked"] is True
    assert any("budget_blocked" in w for w in d["warnings"])
    costs = client.get(f"/projects/{p['id']}/cost-records").json()
    assert any(
        c["status"] == "blocked"
        and c["blocked_reason"] == "expensive_daily_budget_exceeded"
        for c in costs
    )


def test_preview_route_records_planned_for_normal():
    p = client.post(
        "/projects", json={"name": "B76b", "description": "d"}
    ).json()
    r = client.post(
        f"/projects/{p['id']}/model-route/preview",
        json={"workflow_type": "planning"},
    )
    assert r.status_code == 200
    assert r.json()["selected_provider"] == "deepseek"
    costs = client.get(f"/projects/{p['id']}/cost-records").json()
    assert any(c["status"] == "planned" and c["routing_reason"]
               for c in costs)
