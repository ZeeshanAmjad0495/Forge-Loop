"""Task 93 — Temporal Phase B adapter + one migrated workflow.

The Temporal adapter is optional/config-gated and falls back to the
local DB/in-memory engine (no temporalio dependency; tests offline).
incident_to_triage is the one workflow migrated onto the engine
abstraction; the IncidentAnalysis row stays the source of truth.
"""

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import workflow_engine as we

client = TestClient(app)


def _reset():
    from app.repositories_state import repos

    repos.reset_all()
    we.reset_workflow_engine()


def test_temporal_adapter_optional_db_fallback(monkeypatch):
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_PROVIDER", "temporal")
    we.reset_workflow_engine()
    eng = we.get_workflow_engine()
    # Delegates fully to the in-memory/DB engine; usable end to end.
    st = eng.start_workflow(
        "incident_to_triage", "wf-1", {"x": 1}, project_id="p1"
    )
    assert st.status == "running"
    assert eng.get_workflow_status("wf-1") is not None
    assert eng.cancel_workflow("wf-1").status == "cancelled"
    we.reset_workflow_engine()


def _make_incident(pid: str) -> str:
    inc = client.post(
        f"/projects/{pid}/incidents",
        json={
            "title": "prod 500s",
            "description": "elevated 5xx after deploy",
            "severity": "sev3",
            "source": "manual",
        },
    )
    assert inc.status_code == 201, inc.text
    return inc.json()["id"]


def test_incident_to_triage_tracked_on_engine(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_TRACKING_ENABLED", True)
    pid = client.post(
        "/projects", json={"name": "T", "description": "d"}
    ).json()["id"]
    incident_id = _make_incident(pid)
    res = client.post(f"/incidents/{incident_id}/analysis", json={})
    assert res.status_code in (200, 201), res.text
    analysis = res.json()
    assert analysis["status"] in ("completed", "failed")
    eng = we.get_workflow_engine()
    st = eng.get_workflow_status(f"incident_to_triage:{analysis['id']}")
    assert st is not None
    assert st.workflow_type == "incident_to_triage"
    # IncidentAnalysis remains the durable source of truth.
    listed = client.get(f"/incidents/{incident_id}/analyses")
    assert listed.status_code == 200
    assert any(a["id"] == analysis["id"] for a in listed.json())


def test_tracking_disabled_no_workflow_same_analysis(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "WORKFLOW_ENGINE_TRACKING_ENABLED", False)
    pid = client.post(
        "/projects", json={"name": "T2", "description": "d"}
    ).json()["id"]
    incident_id = _make_incident(pid)
    res = client.post(f"/incidents/{incident_id}/analysis", json={})
    assert res.status_code in (200, 201)
    analysis = res.json()
    eng = we.get_workflow_engine()
    assert (
        eng.get_workflow_status(f"incident_to_triage:{analysis['id']}")
        is None
    )
    # Analysis still produced and persisted (source of truth unaffected).
    listed = client.get(f"/incidents/{incident_id}/analyses")
    assert listed.status_code == 200
    assert any(a["id"] == analysis["id"] for a in listed.json())
