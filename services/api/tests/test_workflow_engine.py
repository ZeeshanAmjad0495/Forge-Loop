"""Task 80 Phase A: WorkflowEngine tests. No Temporal required/imported."""

import sys

import pytest

from app import config
from app.services import workflow_engine as we
from app.services.workflow_engine import (
    CANDIDATE_WORKFLOWS,
    HUMAN_APPROVAL_SIGNAL,
    InMemoryWorkflowEngine,
)


def test_start_workflow_running_and_status():
    eng = InMemoryWorkflowEngine()
    st = eng.start_workflow("requirement_to_plan", "w1", {"req": "r1"})
    assert st.status == "running"
    assert st.history[0]["event"] == "started"
    got = eng.get_workflow_status("w1")
    assert got is not None and got.workflow_type == "requirement_to_plan"


def test_start_with_human_approval_wait():
    eng = InMemoryWorkflowEngine()
    st = eng.start_workflow(
        "plan_to_dev_tasks", "w2", awaits_human_approval=True
    )
    assert st.status == "waiting_human_approval"


def test_human_approval_signal_approve_and_reject():
    eng = InMemoryWorkflowEngine()
    eng.start_workflow("plan_to_dev_tasks", "ok", awaits_human_approval=True)
    s = eng.signal_workflow("ok", HUMAN_APPROVAL_SIGNAL, {"approved": True})
    assert s.status == "running"

    eng.start_workflow("plan_to_dev_tasks", "no", awaits_human_approval=True)
    r = eng.signal_workflow("no", HUMAN_APPROVAL_SIGNAL, {"approved": False})
    assert r.status == "cancelled"
    assert r.result.get("reason") == "human_rejected"


def test_signal_unknown_workflow_returns_none():
    eng = InMemoryWorkflowEngine()
    assert eng.signal_workflow("nope", "x") is None


def test_invalid_type_and_duplicate_id():
    eng = InMemoryWorkflowEngine()
    with pytest.raises(ValueError, match="Unknown workflow_type"):
        eng.start_workflow("not_a_workflow", "w")
    eng.start_workflow("incident_to_triage", "dup")
    with pytest.raises(ValueError, match="already exists"):
        eng.start_workflow("incident_to_triage", "dup")


def test_cancel_and_terminal_signal_noop():
    eng = InMemoryWorkflowEngine()
    eng.start_workflow("ci_failure_to_analysis", "c1")
    c = eng.cancel_workflow("c1")
    assert c.status == "cancelled"
    # Signalling a terminal workflow returns it unchanged.
    again = eng.signal_workflow("c1", HUMAN_APPROVAL_SIGNAL, {"approved": True})
    assert again.status == "cancelled"
    assert eng.cancel_workflow("missing") is None


def test_factory_memory_default_and_reset(monkeypatch):
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_PROVIDER", "memory")
    we.reset_workflow_engine()
    e1 = we.get_workflow_engine()
    assert isinstance(e1, InMemoryWorkflowEngine)
    assert we.get_workflow_engine() is e1
    we.reset_workflow_engine()
    assert we.get_workflow_engine() is not e1


def test_temporal_selection_falls_back_to_db_without_import(monkeypatch):
    # Task 93: WORKFLOW_ENGINE_PROVIDER=temporal is now an optional
    # Phase-B adapter that degrades to the local DB/in-memory engine
    # when temporalio is absent (no hard fail, no temporalio import).
    assert "temporalio" not in sys.modules
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_PROVIDER", "temporal")
    we.reset_workflow_engine()
    eng = we.get_workflow_engine()
    assert eng.backend == "temporal_unavailable_fallback_memory"
    h = eng.health_check()
    assert h["temporalio_importable"] is False
    assert h["live_temporal"] is False
    assert h["healthy"] is True
    assert "temporalio" not in sys.modules
    we.reset_workflow_engine()


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_PROVIDER", "airflow")
    we.reset_workflow_engine()
    with pytest.raises(
        RuntimeError, match="Unsupported WORKFLOW_ENGINE_PROVIDER"
    ):
        we.get_workflow_engine()


def test_runtime_summary(monkeypatch):
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_PROVIDER", "memory")
    we.reset_workflow_engine()
    s = we.workflow_engine_runtime_summary()
    assert s["active_backend"] == "memory"
    assert s["is_source_of_truth"] is False
    assert len(s["candidate_workflows"]) == len(CANDIDATE_WORKFLOWS) == 7
    assert s["temporal_adapter"] == "phase_b_seam_db_fallback"


def test_runtime_workflow_route(client):
    res = client.get("/runtime/workflow")
    assert res.status_code == 200
    body = res.json()
    assert body["event_bus"]["active_backend"] == "memory"
    assert body["workflow_engine"]["active_backend"] == "memory"
