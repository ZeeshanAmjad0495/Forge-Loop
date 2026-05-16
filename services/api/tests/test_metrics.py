"""Task 82: free observability tests. No Prometheus/Grafana needed."""

import pytest

from app import config
from app.services import metrics
from app.services.contextpack_builder import (
    ContextPackBuildRequest,
    build_context_pack,
)
from app.services.cost_tracking import record_cost
from app.services.workflow_engine import (
    HUMAN_APPROVAL_SIGNAL,
    InMemoryWorkflowEngine,
)


def test_render_empty_when_no_metrics():
    assert metrics.render() == ""


def test_inc_and_observe_render_prometheus_format():
    metrics.inc("provider_call_total", provider="deepseek")
    metrics.inc("provider_call_total", provider="deepseek")
    metrics.observe("runner_duration_seconds", 1.5, runner="aider")
    out = metrics.render()
    assert "# TYPE provider_call_total counter" in out
    assert 'provider_call_total{provider="deepseek"} 2.0' in out
    assert "# TYPE runner_duration_seconds summary" in out
    assert 'runner_duration_seconds_count{runner="aider"} 1.0' in out
    assert 'runner_duration_seconds_sum{runner="aider"} 1.5' in out


def test_metrics_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(config, "METRICS_ENABLED", False)
    metrics.inc("provider_call_total", provider="x")
    assert metrics.render() == ""


def test_metrics_route_enabled_and_disabled(client, monkeypatch):
    metrics.inc("workflow_started_total", workflow="incident_to_triage")
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "workflow_started_total" in res.text

    monkeypatch.setattr(config, "METRICS_ENABLED", False)
    assert client.get("/metrics").status_code == 404


def test_record_cost_drives_provider_metrics():
    from app.repositories_state import cost_record_repo

    base = dict(
        project_id="p1",
        source_type="model_route",
        source_id="s1",
        workflow_type="manual",
        model="m",
    )
    record_cost(
        cost_record_repo,
        provider="deepseek",
        status="completed",
        estimated_output_cost_usd=0.02,
        **base,
    )
    out = metrics.render()
    assert 'provider_call_total{provider="deepseek"} 1.0' in out
    assert "provider_estimated_cost_usd_total" in out
    # source_type=model_route also drives the route-decision counter.
    assert "llm_route_decision_total" in out

    record_cost(
        cost_record_repo, provider="deepseek", status="failed", **base
    )
    assert "provider_call_failed_total" in metrics.render()

    record_cost(
        cost_record_repo,
        provider="kimi",
        status="blocked",
        was_expensive_provider=True,
        **base,
    )
    assert "kimi_blocked_total" in metrics.render()


def test_contextpack_build_emits_token_metrics(client):
    pr = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    build_context_pack(
        project_id=pr["id"],
        body=ContextPackBuildRequest(active_task_context="word " * 50),
        persist=False,
    )
    out = metrics.render()
    assert "contextpack_tokens_before_total" in out
    assert "contextpack_tokens_after_total" in out


def test_workflow_metrics():
    eng = InMemoryWorkflowEngine()
    eng.start_workflow("incident_to_triage", "w1")
    assert "workflow_started_total" in metrics.render()
    eng.start_workflow("plan_to_dev_tasks", "w2", awaits_human_approval=True)
    eng.signal_workflow("w2", HUMAN_APPROVAL_SIGNAL, {"approved": True})
    assert "approval_wait_seconds_count" in metrics.render()


def test_runner_route_emits_runner_metric(client):
    pr = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    res = client.post(
        f"/projects/{pr['id']}/runner-route/preview", json={}
    )
    assert res.status_code == 200
    assert "runner_selected_total" in metrics.render()


def test_runtime_observability_route(client):
    res = client.get("/runtime/observability")
    assert res.status_code == 200
    data = res.json()
    assert data["metrics_enabled"] is True
    assert data["otel_status"] == "config_flag_only_not_implemented"
    assert data["is_source_of_truth"] is False
