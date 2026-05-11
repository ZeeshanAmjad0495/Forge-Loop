import os
import subprocess
import urllib.request

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.llm.mock import MockLLMProvider

client = TestClient(app)


CI_EVENT_PAYLOAD = {
    "provider": "github_actions",
    "workflow_name": "Backend CI",
    "job_name": "pytest",
    "branch": "feature/example",
    "status": "completed",
    "conclusion": "failure",
    "failure_summary": "pytest failed",
    "logs_excerpt": "E   AssertionError: expected 200, got 500",
}


def _create_project(name: str = "AnaProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_ci_event(project_id: str, extra: dict | None = None) -> dict:
    body = {**CI_EVENT_PAYLOAD, **(extra or {})}
    resp = client.post(f"/projects/{project_id}/ci-events", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create analysis (default provider)
# ---------------------------------------------------------------------------

def test_create_ci_analysis_default_provider_returns_201_completed():
    project = _create_project()
    event = _create_ci_event(project["id"])

    resp = client.post(f"/ci-events/{event['id']}/analysis", json={})
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["ci_event_id"] == event["id"]
    assert a["project_id"] == project["id"]
    assert a["status"] == "completed"
    assert a["provider"] == "mock"
    assert a["model"]
    assert a["error_message"] is None
    assert a["raw_output"]
    # Parsed fields from the mock CI failure response
    assert a["summary"]
    assert isinstance(a["likely_root_causes"], list) and len(a["likely_root_causes"]) >= 1
    assert isinstance(a["suggested_fixes"], list) and len(a["suggested_fixes"]) >= 1
    assert a["recommended_next_action"]
    # The mock response selects code_regression and asks for human review.
    assert a["conclusion"] in (
        "code_regression",
        "needs_human_review",
        "flaky_test",
        "dependency_issue",
        "configuration_issue",
        "infrastructure_issue",
        "unknown",
    )


def test_create_ci_analysis_with_no_body_works():
    project = _create_project()
    event = _create_ci_event(project["id"])
    resp = client.post(f"/ci-events/{event['id']}/analysis")
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Missing event
# ---------------------------------------------------------------------------

def test_create_ci_analysis_missing_event_returns_404():
    resp = client.post("/ci-events/missing/analysis", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Provider override
# ---------------------------------------------------------------------------

def test_create_ci_analysis_explicit_mock_provider_override():
    project = _create_project()
    event = _create_ci_event(project["id"])
    resp = client.post(
        f"/ci-events/{event['id']}/analysis", json={"provider": "mock"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "mock"


def test_create_ci_analysis_unknown_provider_returns_400():
    project = _create_project()
    event = _create_ci_event(project["id"])
    resp = client.post(
        f"/ci-events/{event['id']}/analysis", json={"provider": "nope"}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Failure path: LLM raises
# ---------------------------------------------------------------------------

def test_create_ci_analysis_persists_failed_when_provider_raises(monkeypatch):
    def fail(self, prompt: str) -> str:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(MockLLMProvider, "generate_text", fail)

    project = _create_project()
    event = _create_ci_event(project["id"])
    resp = client.post(f"/ci-events/{event['id']}/analysis", json={})
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["status"] == "failed"
    assert a["conclusion"] == "unknown"
    assert a["error_message"] == "provider exploded"
    assert a["raw_output"] is None

    # Audit ci_analysis_failed must be written.
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("ci_analysis_failed", a["id"]) in actions


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_ci_event_analyses_lists_by_event():
    project = _create_project()
    event = _create_ci_event(project["id"])
    a1 = client.post(f"/ci-events/{event['id']}/analysis", json={}).json()
    a2 = client.post(f"/ci-events/{event['id']}/analysis", json={}).json()

    # Noise: another event with its own analysis.
    other = _create_ci_event(project["id"])
    client.post(f"/ci-events/{other['id']}/analysis", json={})

    resp = client.get(f"/ci-events/{event['id']}/analyses")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert set(ids) == {a1["id"], a2["id"]}


def test_list_ci_event_analyses_missing_event_returns_404():
    resp = client.get("/ci-events/missing/analyses")
    assert resp.status_code == 404


def test_get_ci_analysis_returns_one_and_404_on_missing():
    project = _create_project()
    event = _create_ci_event(project["id"])
    a = client.post(f"/ci-events/{event['id']}/analysis", json={}).json()

    ok = client.get(f"/ci-analyses/{a['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == a["id"]

    miss = client.get("/ci-analyses/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_audit_events_recorded_for_analysis_request_and_completion():
    project = _create_project()
    event = _create_ci_event(project["id"])
    a = client.post(f"/ci-events/{event['id']}/analysis", json={}).json()

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("ci_analysis_requested", a["id"]) in actions
    assert ("ci_analysis_completed", a["id"]) in actions


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_create_ci_analysis_does_not_invoke_subprocess_or_network(monkeypatch):
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
    event = _create_ci_event(project["id"])
    resp = client.post(f"/ci-events/{event['id']}/analysis", json={})
    assert resp.status_code == 201

    assert called == [], f"Unexpected external calls: {called}"
