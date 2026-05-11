import os
import subprocess
import urllib.request

from fastapi.testclient import TestClient

from app.main import app
from app.llm.mock import MockLLMProvider

client = TestClient(app)


INCIDENT_PAYLOAD = {
    "title": "Production API latency spike",
    "description": "Users report increased latency on checkout API.",
    "severity": "sev3",
    "source": "manual",
    "environment": "production",
    "affected_area": "checkout-api",
    "evidence": "p99 latency rose from 200ms to 1800ms over 10m.",
}


def _create_project(name: str = "AnaProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_incident(project_id: str, extra: dict | None = None) -> dict:
    body = {**INCIDENT_PAYLOAD, **(extra or {})}
    resp = client.post(f"/projects/{project_id}/incidents", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create analysis (default provider)
# ---------------------------------------------------------------------------

def test_create_incident_analysis_default_provider_returns_201_completed():
    project = _create_project()
    inc = _create_incident(project["id"])

    resp = client.post(f"/incidents/{inc['id']}/analysis", json={})
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["incident_id"] == inc["id"]
    assert a["project_id"] == project["id"]
    assert a["status"] == "completed"
    assert a["provider"] == "mock"
    assert a["model"]
    assert a["error_message"] is None
    assert a["raw_output"]
    from app.main import artifact_repo
    assert a["artifact_id"] is not None
    artifact = artifact_repo.get(a["artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type == "incident_analysis"
    assert artifact.content == a["raw_output"]
    assert a["summary"]
    assert isinstance(a["likely_root_causes"], list) and len(a["likely_root_causes"]) >= 1
    assert isinstance(a["remediation_plan"], list) and len(a["remediation_plan"]) >= 1
    assert isinstance(a["prevention_actions"], list)
    assert isinstance(a["immediate_actions"], list)
    assert a["recommended_next_action"]
    assert a["conclusion"] in (
        "code_regression",
        "configuration_issue",
        "infrastructure_issue",
        "dependency_issue",
        "data_issue",
        "security_issue",
        "flaky_external_service",
        "needs_human_review",
        "unknown",
    )


def test_create_incident_analysis_with_no_body_works():
    project = _create_project()
    inc = _create_incident(project["id"])
    resp = client.post(f"/incidents/{inc['id']}/analysis")
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Missing incident
# ---------------------------------------------------------------------------

def test_create_incident_analysis_missing_incident_returns_404():
    resp = client.post("/incidents/missing/analysis", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Provider override
# ---------------------------------------------------------------------------

def test_create_incident_analysis_explicit_mock_provider_override():
    project = _create_project()
    inc = _create_incident(project["id"])
    resp = client.post(
        f"/incidents/{inc['id']}/analysis", json={"provider": "mock"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "mock"


def test_create_incident_analysis_unknown_provider_returns_400():
    project = _create_project()
    inc = _create_incident(project["id"])
    resp = client.post(
        f"/incidents/{inc['id']}/analysis", json={"provider": "nope"}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Failure path: LLM raises
# ---------------------------------------------------------------------------

def test_create_incident_analysis_persists_failed_when_provider_raises(monkeypatch):
    def fail(self, prompt: str) -> str:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(MockLLMProvider, "generate_text", fail)

    project = _create_project()
    inc = _create_incident(project["id"])
    resp = client.post(f"/incidents/{inc['id']}/analysis", json={})
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["status"] == "failed"
    assert a["conclusion"] == "unknown"
    assert a["error_message"] == "provider exploded"
    assert a["raw_output"] is None

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("incident_analysis_failed", a["id"]) in actions


# ---------------------------------------------------------------------------
# Linked context propagated to prompt
# ---------------------------------------------------------------------------

def test_incident_analysis_prompt_includes_only_linked_context(monkeypatch):
    captured: dict = {}

    def capture(self, prompt: str) -> str:
        captured["prompt"] = prompt
        return "## 1. Incident Summary\n\nstub"

    monkeypatch.setattr(MockLLMProvider, "generate_text", capture)

    # Incident with no links: prompt should not name CI/PR/dev task.
    project = _create_project()
    inc = _create_incident(project["id"])
    client.post(f"/incidents/{inc['id']}/analysis", json={})
    assert "Linked items" in captured["prompt"]
    assert "(none)" in captured["prompt"]
    assert "PR draft title" not in captured["prompt"]
    assert "Dev task title" not in captured["prompt"]


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_incident_analyses_lists_by_incident():
    project = _create_project()
    inc = _create_incident(project["id"])
    a1 = client.post(f"/incidents/{inc['id']}/analysis", json={}).json()
    a2 = client.post(f"/incidents/{inc['id']}/analysis", json={}).json()

    other = _create_incident(project["id"])
    client.post(f"/incidents/{other['id']}/analysis", json={})

    resp = client.get(f"/incidents/{inc['id']}/analyses")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert set(ids) == {a1["id"], a2["id"]}


def test_list_incident_analyses_missing_incident_returns_404():
    resp = client.get("/incidents/missing/analyses")
    assert resp.status_code == 404


def test_get_incident_analysis_returns_one_and_404_on_missing():
    project = _create_project()
    inc = _create_incident(project["id"])
    a = client.post(f"/incidents/{inc['id']}/analysis", json={}).json()

    ok = client.get(f"/incident-analyses/{a['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == a["id"]

    miss = client.get("/incident-analyses/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_audit_events_recorded_for_analysis_request_and_completion():
    project = _create_project()
    inc = _create_incident(project["id"])
    a = client.post(f"/incidents/{inc['id']}/analysis", json={}).json()

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("incident_analysis_requested", a["id"]) in actions
    assert ("incident_analysis_completed", a["id"]) in actions


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_create_incident_analysis_does_not_invoke_subprocess_or_network(monkeypatch):
    called: list[tuple] = []

    def fake_run(*args, **kwargs):
        called.append(("subprocess.run", args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    def fake_urlopen(*args, **kwargs):
        called.append(("urlopen", args))
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    project = _create_project()
    inc = _create_incident(project["id"])
    resp = client.post(f"/incidents/{inc['id']}/analysis", json={})
    assert resp.status_code == 201
    assert called == [], f"Unexpected external calls: {called}"
