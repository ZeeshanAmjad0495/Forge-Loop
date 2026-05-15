import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}

RUNNER_DEF_PAYLOAD = {
    "name": "OpenHands",
    "runner_type": "openhands",
    "enabled": False,
    "mode": "dry_run",
    "description": "Primary coding runner",
    "config": {"notes": "No execution yet"},
}

TOOL_RUN_PAYLOAD_BASE = {
    "target_type": "manual",
    "target_id": "manual-run-1",
    "runner_type": "manual",
    "mode": "manual",
    "status": "completed",
    "conclusion": "success",
    "summary": "Manual implementation completed",
}


def _create_project(name: str = "TestProject") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD).json()


def _create_definition(project_id: str, payload: dict | None = None) -> dict:
    return client.post(
        f"/projects/{project_id}/tool-runner-definitions",
        json=payload or RUNNER_DEF_PAYLOAD,
    ).json()


# ---------------------------------------------------------------------------
# ToolRunnerDefinition CRUD
# ---------------------------------------------------------------------------

def test_create_tool_runner_definition_returns_201_and_shape():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json=RUNNER_DEF_PAYLOAD,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["name"] == "OpenHands"
    assert data["runner_type"] == "openhands"
    assert data["enabled"] is False
    assert data["mode"] == "dry_run"
    assert data["description"] == "Primary coding runner"
    assert data["config"] == {"notes": "No execution yet"}
    assert data["code_repository_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_tool_runner_definition_with_repo():
    project = _create_project()
    repo = _create_repo(project["id"])
    payload = {**RUNNER_DEF_PAYLOAD, "code_repository_id": repo["id"]}
    resp = client.post(f"/projects/{project['id']}/tool-runner-definitions", json=payload)
    assert resp.status_code == 201
    assert resp.json()["code_repository_id"] == repo["id"]


def test_create_tool_runner_definition_unknown_project_returns_404():
    resp = client.post("/projects/nonexistent/tool-runner-definitions", json=RUNNER_DEF_PAYLOAD)
    assert resp.status_code == 404


def test_create_tool_runner_definition_unknown_repo_returns_404():
    project = _create_project()
    payload = {**RUNNER_DEF_PAYLOAD, "code_repository_id": "no-such-repo"}
    resp = client.post(f"/projects/{project['id']}/tool-runner-definitions", json=payload)
    assert resp.status_code == 404


def test_create_tool_runner_definition_rejects_secret_keys_in_config():
    project = _create_project()
    payload = {**RUNNER_DEF_PAYLOAD, "config": {"api_key": "should-not-store"}}
    resp = client.post(f"/projects/{project['id']}/tool-runner-definitions", json=payload)
    assert resp.status_code == 400
    assert "api_key" in resp.json()["detail"]


def test_create_tool_runner_definition_rejects_token_in_config():
    project = _create_project()
    payload = {**RUNNER_DEF_PAYLOAD, "config": {"token": "abc"}}
    resp = client.post(f"/projects/{project['id']}/tool-runner-definitions", json=payload)
    assert resp.status_code == 400


def test_list_project_tool_runner_definitions():
    project = _create_project()
    _create_definition(project["id"])
    _create_definition(project["id"], {**RUNNER_DEF_PAYLOAD, "name": "Manual Runner", "runner_type": "manual", "mode": "manual", "enabled": True})
    resp = client.get(f"/projects/{project['id']}/tool-runner-definitions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    names = {d["name"] for d in items}
    assert "OpenHands" in names
    assert "Manual Runner" in names


def test_list_project_tool_runner_definitions_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/tool-runner-definitions")
    assert resp.status_code == 404


def test_get_tool_runner_definition():
    project = _create_project()
    created = _create_definition(project["id"])
    resp = client.get(f"/tool-runner-definitions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_tool_runner_definition_404():
    resp = client.get("/tool-runner-definitions/nonexistent")
    assert resp.status_code == 404


def test_patch_tool_runner_definition_updates_fields_and_preserves_others():
    project = _create_project()
    created = _create_definition(project["id"])
    resp = client.patch(
        f"/tool-runner-definitions/{created['id']}",
        json={"name": "OpenHands Renamed", "enabled": True, "mode": "api"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "OpenHands Renamed"
    assert data["enabled"] is True
    assert data["mode"] == "api"
    # Unchanged fields preserved
    assert data["runner_type"] == "openhands"
    assert data["description"] == "Primary coding runner"


def test_patch_tool_runner_definition_rejects_secret_config():
    project = _create_project()
    created = _create_definition(project["id"])
    resp = client.patch(
        f"/tool-runner-definitions/{created['id']}",
        json={"config": {"password": "hunter2"}},
    )
    assert resp.status_code == 400


def test_patch_tool_runner_definition_writes_audit_with_changed_fields():
    project = _create_project()
    created = _create_definition(project["id"])
    client.patch(f"/tool-runner-definitions/{created['id']}", json={"name": "Updated"})
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    patch_events = [e for e in events if e["action"] == "tool_runner_definition_updated"]
    assert len(patch_events) >= 1
    assert "name" in patch_events[0]["details"]["changed_fields"]


def test_patch_tool_runner_definition_404():
    resp = client.patch("/tool-runner-definitions/nonexistent", json={"name": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Defaults endpoint
# ---------------------------------------------------------------------------

def test_defaults_creates_openhands_and_manual_definitions():
    project = _create_project()
    resp = client.post(f"/projects/{project['id']}/tool-runner-definitions/defaults", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["created"]) == 2
    assert len(data["existing"]) == 0
    names = {d["name"] for d in data["created"]}
    assert "OpenHands" in names
    assert "Manual Runner" in names
    openhands = next(d for d in data["created"] if d["name"] == "OpenHands")
    manual = next(d for d in data["created"] if d["name"] == "Manual Runner")
    # B4: OpenHands runner is now seeded enabled. Execution remains gated
    # by OPENHANDS_EXECUTION_ENABLED + request mode, so this is safe.
    assert openhands["enabled"] is True
    assert openhands["mode"] == "dry_run"
    assert manual["enabled"] is True
    assert manual["mode"] == "manual"


def test_defaults_dedupes_existing_definitions():
    project = _create_project()
    # First call creates both
    resp1 = client.post(f"/projects/{project['id']}/tool-runner-definitions/defaults", json={})
    assert resp1.status_code == 201
    assert len(resp1.json()["created"]) == 2

    # Second call finds both already existing
    resp2 = client.post(f"/projects/{project['id']}/tool-runner-definitions/defaults", json={})
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert len(data2["created"]) == 0
    assert len(data2["existing"]) == 2


def test_defaults_unknown_project_returns_404():
    resp = client.post("/projects/nonexistent/tool-runner-definitions/defaults", json={})
    assert resp.status_code == 404


def test_defaults_unknown_repo_returns_404():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/tool-runner-definitions/defaults",
        json={"code_repository_id": "no-such-repo"},
    )
    assert resp.status_code == 404


def test_defaults_creates_audit_events():
    project = _create_project()
    client.post(f"/projects/{project['id']}/tool-runner-definitions/defaults", json={})
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    created_events = [e for e in events if e["action"] == "tool_runner_definition_created"]
    assert len(created_events) == 2
    sources = {e["details"].get("source") for e in created_events}
    assert sources == {"defaults"}


def test_defaults_scoped_to_repo_dedupes_per_repo():
    project = _create_project()
    repo = _create_repo(project["id"])
    # Call once with repo scope
    resp1 = client.post(
        f"/projects/{project['id']}/tool-runner-definitions/defaults",
        json={"code_repository_id": repo["id"]},
    )
    assert resp1.status_code == 201
    assert len(resp1.json()["created"]) == 2

    # Call again — should find existing
    resp2 = client.post(
        f"/projects/{project['id']}/tool-runner-definitions/defaults",
        json={"code_repository_id": repo["id"]},
    )
    assert len(resp2.json()["created"]) == 0
    assert len(resp2.json()["existing"]) == 2


# ---------------------------------------------------------------------------
# ToolRun CRUD
# ---------------------------------------------------------------------------

def test_record_tool_run_returns_201_and_shape():
    project = _create_project()
    payload = {**TOOL_RUN_PAYLOAD_BASE, "project_id": project["id"]}
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["runner_type"] == "manual"
    assert data["target_type"] == "manual"
    assert data["status"] == "completed"
    assert data["conclusion"] == "success"
    assert data["summary"] == "Manual implementation completed"
    assert data["code_repository_id"] is None
    assert data["tool_runner_definition_id"] is None
    assert data["artifact_id"] is None
    assert "id" in data
    assert "started_at" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_record_tool_run_links_artifact_when_output_present():
    from app.main import artifact_repo

    project = _create_project()
    payload = {
        **TOOL_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "output": "patch applied",
    }
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["artifact_id"] is not None
    artifact = artifact_repo.get(data["artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type == "tool_run_result"
    assert artifact.content == "patch applied"


def test_record_tool_run_unknown_project_returns_404():
    payload = {**TOOL_RUN_PAYLOAD_BASE, "project_id": "nonexistent"}
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 404


def test_record_tool_run_unknown_repo_returns_404():
    project = _create_project()
    payload = {**TOOL_RUN_PAYLOAD_BASE, "project_id": project["id"], "code_repository_id": "no-repo"}
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 404


def test_record_tool_run_with_definition():
    project = _create_project()
    defn = _create_definition(project["id"])
    payload = {
        **TOOL_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "tool_runner_definition_id": defn["id"],
        "runner_type": "openhands",
        "mode": "dry_run",
    }
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 201
    assert resp.json()["tool_runner_definition_id"] == defn["id"]


def test_record_tool_run_unknown_definition_returns_404():
    project = _create_project()
    payload = {
        **TOOL_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "tool_runner_definition_id": "does-not-exist",
    }
    resp = client.post("/tool-runs", json=payload)
    assert resp.status_code == 404


def test_record_tool_run_writes_audit_event():
    project = _create_project()
    client.post("/tool-runs", json={**TOOL_RUN_PAYLOAD_BASE, "project_id": project["id"]})
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "tool_run_recorded" for e in events)


def test_list_project_tool_runs_filters_by_project():
    p1 = _create_project("P1")
    p2 = _create_project("P2")
    client.post("/tool-runs", json={**TOOL_RUN_PAYLOAD_BASE, "project_id": p1["id"]})
    client.post("/tool-runs", json={**TOOL_RUN_PAYLOAD_BASE, "project_id": p2["id"]})
    resp = client.get(f"/projects/{p1['id']}/tool-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["project_id"] == p1["id"]


def test_list_project_tool_runs_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/tool-runs")
    assert resp.status_code == 404


def test_get_tool_run():
    project = _create_project()
    created = client.post("/tool-runs", json={**TOOL_RUN_PAYLOAD_BASE, "project_id": project["id"]}).json()
    resp = client.get(f"/tool-runs/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_tool_run_404():
    resp = client.get("/tool-runs/nonexistent")
    assert resp.status_code == 404


def test_list_dev_task_tool_runs_filters_by_target():
    project = _create_project()
    # Create dev task via decomposition
    req = client.post(
        f"/projects/{project['id']}/requirements",
        json={"title": "Sample req", "problem_statement": "Test."},
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    task = decomp["dev_tasks"][0]

    client.post("/tool-runs", json={
        "project_id": project["id"],
        "target_type": "dev_task",
        "target_id": task["id"],
        "runner_type": "manual",
        "mode": "manual",
        "status": "completed",
        "conclusion": "success",
        "summary": "done",
    })
    client.post("/tool-runs", json={
        **TOOL_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "target_id": "other-task",
    })

    resp = client.get(f"/dev-tasks/{task['id']}/tool-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["target_type"] == "dev_task"
    assert runs[0]["target_id"] == task["id"]


def test_list_dev_task_tool_runs_unknown_dev_task_returns_404():
    resp = client.get("/dev-tasks/nonexistent/tool-runs")
    assert resp.status_code == 404


def test_list_subtask_tool_runs_filters_by_target():
    project = _create_project()
    req = client.post(
        f"/projects/{project['id']}/requirements",
        json={"title": "Subtask req", "problem_statement": "Test."},
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    task = decomp["dev_tasks"][0]
    subtasks = client.get(f"/dev-tasks/{task['id']}/subtasks").json()

    if not subtasks:
        pytest.skip("No subtasks generated by mock — skip subtask filter test")

    subtask = subtasks[0]
    client.post("/tool-runs", json={
        "project_id": project["id"],
        "target_type": "subtask",
        "target_id": subtask["id"],
        "runner_type": "manual",
        "mode": "manual",
        "status": "completed",
        "conclusion": "success",
        "summary": "subtask done",
    })

    resp = client.get(f"/subtasks/{subtask['id']}/tool-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["target_id"] == subtask["id"]


def test_list_subtask_tool_runs_unknown_subtask_returns_404():
    resp = client.get("/subtasks/nonexistent/tool-runs")
    assert resp.status_code == 404


def test_record_tool_run_does_not_execute_subprocess_or_network(monkeypatch):
    called = []

    def fake_run(*args, **kwargs):
        called.append(("subprocess.run", args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)

    project = _create_project()
    resp = client.post("/tool-runs", json={**TOOL_RUN_PAYLOAD_BASE, "project_id": project["id"]})
    assert resp.status_code == 201
    assert called == [], f"Unexpected external command calls: {called}"
