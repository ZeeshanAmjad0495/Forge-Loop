import os
import subprocess
import urllib.request

from fastapi.testclient import TestClient

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

INCIDENT_PAYLOAD = {
    "title": "Production API latency spike",
    "description": "Users report increased latency on checkout API.",
    "severity": "sev3",
    "source": "manual",
    "environment": "production",
    "affected_area": "checkout-api",
    "evidence": "p99 latency rose from 200ms to 1800ms over 10m.",
}


def _create_project(name: str = "MemProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_ci_analysis(project_id: str) -> dict:
    event = client.post(
        f"/projects/{project_id}/ci-events", json=CI_EVENT_PAYLOAD
    ).json()
    return client.post(f"/ci-events/{event['id']}/analysis", json={}).json()


def _create_incident_analysis(project_id: str) -> dict:
    inc = client.post(
        f"/projects/{project_id}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    return client.post(f"/incidents/{inc['id']}/analysis", json={}).json()


def _create_check_run(project_id: str) -> dict:
    return client.post("/check-runs", json={
        "project_id": project_id,
        "target_type": "dev_task",
        "target_id": "abc-task",
        "status": "completed",
        "conclusion": "failure",
        "summary": "pytest failed",
        "output": "E   AssertionError: expected 200, got 500",
    }).json()


# ---------------------------------------------------------------------------
# Create learning run from each supported source
# ---------------------------------------------------------------------------

def test_learning_run_from_ci_analysis_creates_candidates():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])

    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "completed"
    assert run["source_type"] == "ci_analysis"
    assert run["source_id"] == analysis["id"]
    assert run["provider"] == "mock"
    assert run["candidates_created"] >= 1
    assert len(run["candidate_ids"]) == run["candidates_created"]
    assert run["error_message"] is None
    assert run["raw_output"]
    assert run["summary"]

    from app.main import artifact_repo
    assert run["artifact_id"] is not None
    run_artifact = artifact_repo._store[run["artifact_id"]]
    assert run_artifact.artifact_type == "memory_learning_summary"
    assert run_artifact.content == run["raw_output"]

    # Candidates are persisted and linked back to the run.
    cands = client.get(f"/projects/{project['id']}/memory-candidates").json()
    assert len(cands) == run["candidates_created"]
    assert all(c["learning_run_id"] == run["id"] for c in cands)
    assert all(c["status"] == "proposed" for c in cands)
    assert all(c["source_type"] == "ci_analysis" for c in cands)
    for c in cands:
        assert c["artifact_id"] is not None
        cand_artifact = artifact_repo._store[c["artifact_id"]]
        assert cand_artifact.artifact_type == "memory_candidate_batch"


def test_learning_run_from_incident_analysis_works():
    project = _create_project()
    analysis = _create_incident_analysis(project["id"])

    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "incident_analysis", "source_id": analysis["id"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "completed"


def test_learning_run_from_check_run_works():
    project = _create_project()
    cr = _create_check_run(project["id"])

    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "check_run", "source_id": cr["id"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# 404 / 400 paths
# ---------------------------------------------------------------------------

def test_learning_run_missing_project_returns_404():
    resp = client.post(
        "/projects/missing/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": "x"},
    )
    assert resp.status_code == 404


def test_learning_run_missing_ci_analysis_source_returns_404():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": "missing"},
    )
    assert resp.status_code == 404


def test_learning_run_missing_incident_analysis_source_returns_404():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "incident_analysis", "source_id": "missing"},
    )
    assert resp.status_code == 404


def test_learning_run_unsupported_source_type_returns_400():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "audit_event", "source_id": "x"},
    )
    assert resp.status_code == 400


def test_learning_run_manual_source_type_returns_400():
    project = _create_project()
    # `manual` is allowed for candidates but not as a learning-run input.
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "manual", "source_id": "x"},
    )
    assert resp.status_code == 400


def test_learning_run_unknown_provider_returns_400():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={
            "source_type": "ci_analysis",
            "source_id": analysis["id"],
            "provider": "nope",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Provider override + LLM failure
# ---------------------------------------------------------------------------

def test_learning_run_explicit_mock_provider_override():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={
            "source_type": "ci_analysis",
            "source_id": analysis["id"],
            "provider": "mock",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "mock"


def test_learning_run_persists_failed_when_provider_raises(monkeypatch):
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])

    def fail(self, prompt: str) -> str:
        # Only fail the memory-learning prompt, not the CI analysis prompt
        # used during fixture creation.
        if "Project Memory Learning" in prompt:
            raise RuntimeError("provider exploded")
        return "stub"

    monkeypatch.setattr(MockLLMProvider, "generate_text", fail)

    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "failed"
    assert run["error_message"] == "provider exploded"
    assert run["candidates_created"] == 0
    assert run["candidate_ids"] == []
    assert run["raw_output"] is None

    # No candidates were persisted.
    cands = client.get(f"/projects/{project['id']}/memory-candidates").json()
    assert cands == []

    # Audit memory_learning_failed must be written.
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("memory_learning_failed", run["id"]) in actions


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_learning_runs_lists_by_project():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])
    r1 = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    ).json()
    r2 = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    ).json()

    other_project = _create_project("Other")
    other_analysis = _create_ci_analysis(other_project["id"])
    client.post(
        f"/projects/{other_project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": other_analysis["id"]},
    )

    resp = client.get(f"/projects/{project['id']}/memory-learning-runs")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert set(ids) == {r1["id"], r2["id"]}


def test_list_learning_runs_missing_project_returns_404():
    resp = client.get("/projects/missing/memory-learning-runs")
    assert resp.status_code == 404


def test_get_learning_run_returns_one_and_404_on_missing():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])
    run = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    ).json()

    ok = client.get(f"/memory-learning-runs/{run['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == run["id"]

    miss = client.get("/memory-learning-runs/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_learning_run_writes_request_and_completion_audit_events():
    project = _create_project()
    analysis = _create_ci_analysis(project["id"])
    run = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    ).json()

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("memory_learning_requested", run["id"]) in actions
    assert ("memory_learning_completed", run["id"]) in actions
    # One memory_candidate_created per candidate.
    created_count = sum(1 for a, _ in actions if a == "memory_candidate_created")
    assert created_count == run["candidates_created"]


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_learning_run_does_not_invoke_subprocess_or_network(monkeypatch):
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
    analysis = _create_ci_analysis(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/memory-learning-runs",
        json={"source_type": "ci_analysis", "source_id": analysis["id"]},
    )
    assert resp.status_code == 201
    assert called == [], f"Unexpected external calls: {called}"
