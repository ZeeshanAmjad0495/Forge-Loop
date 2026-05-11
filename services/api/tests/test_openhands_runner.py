import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.tool_runners.openhands import OpenHandsRunner

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}

SAFETY_PAYLOAD = {
    "work_safe_mode": True,
    "allowed_actions": ["read_code", "propose_changes"],
    "blocked_paths": [".env", "secrets/"],
    "required_checks": ["tests", "build"],
    "requires_approval_for": ["create_pr"],
    "protected_branches": ["main"],
    "notes": "",
}

REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


def _create_project(name: str = "OHProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD
    ).json()


def _set_safety(repo_id: str, payload: dict | None = None) -> dict:
    return client.post(
        f"/code-repositories/{repo_id}/safety-profile", json=payload or SAFETY_PAYLOAD
    ).json()


def _create_dev_task(project_id: str | None = None) -> dict:
    project = client.post("/projects", json={"name": "P1", "description": "d"}).json() \
        if project_id is None else {"id": project_id}
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    task = decomp["dev_tasks"][0]
    return task


# ---------------------------------------------------------------------------
# Prepare endpoint
# ---------------------------------------------------------------------------

def test_prepare_package_for_dev_task_returns_201_and_shape():
    task = _create_dev_task()
    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert "tool_run" in data
    assert "instruction_package" in data

    pkg = data["instruction_package"]
    assert pkg["schema_version"] == "1"
    assert pkg["runner"] == "openhands"
    assert pkg["mode"] == "dry_run"
    assert pkg["project"]["id"] == task["project_id"]
    assert pkg["dev_task"]["id"] == task["id"]
    assert isinstance(pkg["instructions"], list)
    assert any("Do not open pull requests" in s for s in pkg["instructions"])

    run = data["tool_run"]
    assert run["runner_type"] == "openhands"
    assert run["mode"] == "dry_run"
    assert run["status"] == "completed"
    assert run["conclusion"] == "requires_human_action"
    assert run["target_type"] == "dev_task"
    assert run["target_id"] == task["id"]
    assert run["summary"] == "OpenHands instruction package prepared"
    assert run["output"] is not None
    parsed = json.loads(run["output"])
    assert parsed["dev_task"]["id"] == task["id"]

    from app.main import artifact_repo
    assert run["artifact_id"] is not None
    artifact = artifact_repo.get(run["artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type == "openhands_instruction_package"
    assert artifact.content == run["output"]


def test_prepare_package_includes_task_title_description_and_acceptance_criteria():
    task = _create_dev_task()
    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    pkg = resp.json()["instruction_package"]
    assert pkg["dev_task"]["title"] == task["title"]
    assert pkg["dev_task"]["description"] == task["description"]
    assert pkg["dev_task"]["acceptance_criteria"] == task["acceptance_criteria"]
    assert pkg["dev_task"]["definition_of_done"] == task["definition_of_done"]


def test_prepare_package_includes_safety_constraints_when_profile_present():
    project = _create_project()
    repo = _create_repo(project["id"])
    _set_safety(repo["id"])
    task = _create_dev_task(project["id"])

    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    assert resp.status_code == 201
    pkg = resp.json()["instruction_package"]
    safety = pkg["safety"]
    assert safety is not None
    assert ".env" in safety["blocked_paths"]
    assert "tests" in safety["required_checks"]
    assert "main" in safety["protected_branches"]
    assert pkg["repository"]["id"] == repo["id"]
    assert any("protected branches" in s.lower() for s in pkg["instructions"])


def test_prepare_package_omits_safety_when_no_profile():
    project = _create_project()
    task = _create_dev_task(project["id"])
    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    pkg = resp.json()["instruction_package"]
    assert pkg["safety"] is None
    assert pkg["repository"] is None
    assert any("No repo safety profile" in s for s in pkg["instructions"])


def test_prepare_package_records_tool_run_with_correct_fields():
    task = _create_dev_task()
    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    run_id = resp.json()["tool_run"]["id"]

    listing = client.get(f"/dev-tasks/{task['id']}/tool-runs").json()
    assert any(r["id"] == run_id for r in listing)

    fetched = client.get(f"/tool-runs/{run_id}").json()
    assert fetched["runner_type"] == "openhands"
    assert fetched["mode"] == "dry_run"
    assert fetched["status"] == "completed"
    assert fetched["conclusion"] == "requires_human_action"
    assert fetched["output"] is not None
    json.loads(fetched["output"])  # valid JSON


def test_prepare_package_writes_audit_event():
    task = _create_dev_task()
    client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    events = client.get(f"/projects/{task['project_id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "openhands_package_prepared" in actions


def test_prepare_package_unknown_dev_task_returns_404():
    resp = client.post("/dev-tasks/nonexistent/openhands/prepare", json={})
    assert resp.status_code == 404


def test_prepare_package_unknown_definition_returns_404():
    task = _create_dev_task()
    resp = client.post(
        f"/dev-tasks/{task['id']}/openhands/prepare",
        json={"tool_runner_definition_id": "nonexistent"},
    )
    assert resp.status_code == 404


def test_prepare_package_rejects_non_openhands_definition():
    project = _create_project()
    task = _create_dev_task(project["id"])
    defn = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json={
            "name": "Manual",
            "runner_type": "manual",
            "enabled": True,
            "mode": "manual",
            "description": "",
            "config": {},
        },
    ).json()
    resp = client.post(
        f"/dev-tasks/{task['id']}/openhands/prepare",
        json={"tool_runner_definition_id": defn["id"]},
    )
    assert resp.status_code == 400


def test_prepare_package_rejects_disabled_definition():
    project = _create_project()
    task = _create_dev_task(project["id"])
    defn = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json={
            "name": "OpenHands",
            "runner_type": "openhands",
            "enabled": False,
            "mode": "dry_run",
            "description": "",
            "config": {},
        },
    ).json()
    resp = client.post(
        f"/dev-tasks/{task['id']}/openhands/prepare",
        json={"tool_runner_definition_id": defn["id"]},
    )
    assert resp.status_code == 400


def test_prepare_package_does_not_invoke_subprocess_or_network(monkeypatch):
    called: list[tuple] = []

    def fake_run(*args, **kwargs):
        called.append(("subprocess.run", args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)

    task = _create_dev_task()
    resp = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={})
    assert resp.status_code == 201
    assert called == [], f"Unexpected external command calls: {called}"


# ---------------------------------------------------------------------------
# Record-result endpoint
# ---------------------------------------------------------------------------

def test_record_result_updates_tool_run_and_writes_audit():
    task = _create_dev_task()
    prep = client.post(f"/dev-tasks/{task['id']}/openhands/prepare", json={}).json()
    run_id = prep["tool_run"]["id"]

    resp = client.post(
        f"/tool-runs/{run_id}/openhands/record-result",
        json={"summary": "Done", "output": "diff goes here", "conclusion": "success"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == "Done"
    assert data["output"] == "diff goes here"
    assert data["conclusion"] == "success"
    assert data["completed_at"] is not None

    events = client.get(f"/projects/{task['project_id']}/audit-events").json()
    assert any(e["action"] == "openhands_result_recorded" for e in events)


def test_record_result_unknown_tool_run_returns_404():
    resp = client.post(
        "/tool-runs/nonexistent/openhands/record-result",
        json={"summary": "x", "output": "y", "conclusion": "neutral"},
    )
    assert resp.status_code == 404


def test_record_result_rejects_non_openhands_run():
    project = _create_project()
    other = client.post(
        "/tool-runs",
        json={
            "project_id": project["id"],
            "target_type": "manual",
            "target_id": "m1",
            "runner_type": "manual",
            "mode": "manual",
            "status": "completed",
            "conclusion": "success",
            "summary": "manual",
        },
    ).json()
    resp = client.post(
        f"/tool-runs/{other['id']}/openhands/record-result",
        json={"summary": "x", "output": "y", "conclusion": "success"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Execution gating
# ---------------------------------------------------------------------------

def test_openhands_runner_execute_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", False)
    runner = OpenHandsRunner()
    with pytest.raises(NotImplementedError):
        runner.execute()


def test_openhands_runner_execute_still_not_implemented_when_flag_true(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", True)
    runner = OpenHandsRunner()
    with pytest.raises(NotImplementedError):
        runner.execute()
