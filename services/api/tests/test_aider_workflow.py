"""Tests for C1: the Aider tool-runner adapter + workflow.

The runner is pure (instruction package only); no subprocess / network /
LLM is invoked. Mirrors the OpenHands prepare/record contract.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


def _project() -> dict:
    return client.post("/projects", json={"name": "PC1", "description": "d"}).json()


def _dev_task(project_id: str) -> dict:
    req = client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()
    return decomp["dev_tasks"][0]


def test_prepare_aider_package_returns_tool_run_and_package():
    project = _project()
    task = _dev_task(project["id"])

    res = client.post(f"/dev-tasks/{task['id']}/aider/prepare", json={})
    assert res.status_code == 201, res.text
    run = res.json()
    assert run["runner_type"] == "aider"
    assert run["mode"] == "dry_run"
    assert run["target_type"] == "dev_task"
    assert run["target_id"] == task["id"]
    assert run["artifact_id"]

    pkg = json.loads(run["output"])
    assert pkg["runner"] == "aider"
    assert pkg["dev_task"]["id"] == task["id"]
    # LLM identity is recorded — Aider defaults to local Ollama. Never a key.
    assert "llm" in pkg
    assert pkg["llm"]["provider"] == "ollama"
    assert pkg["llm"]["model"]  # OLLAMA_DEFAULT_MODEL
    assert pkg["llm"]["base_url"].startswith("http")
    assert all("key" not in k.lower() for k in pkg["llm"])

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "aider_package_prepared" for e in events)


def test_prepare_aider_package_unknown_dev_task_404():
    res = client.post("/dev-tasks/nope/aider/prepare", json={})
    assert res.status_code == 404


def test_prepare_aider_rejects_non_aider_definition():
    project = _project()
    task = _dev_task(project["id"])
    # An OpenHands runner definition must not be usable on the Aider path.
    definition = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json={
            "name": "OpenHands",
            "runner_type": "openhands",
            "enabled": True,
            "mode": "dry_run",
            "description": "x",
            "config": {},
        },
    ).json()

    res = client.post(
        f"/dev-tasks/{task['id']}/aider/prepare",
        json={"tool_runner_definition_id": definition["id"]},
    )
    assert res.status_code == 400
    assert "not an Aider runner" in res.text


def test_prepare_aider_rejects_disabled_definition():
    project = _project()
    task = _dev_task(project["id"])
    definition = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json={
            "name": "Aider",
            "runner_type": "aider",
            "enabled": False,
            "mode": "dry_run",
            "description": "x",
            "config": {},
        },
    ).json()
    res = client.post(
        f"/dev-tasks/{task['id']}/aider/prepare",
        json={"tool_runner_definition_id": definition["id"]},
    )
    assert res.status_code == 400
    assert "disabled" in res.text


def test_record_aider_result_updates_tool_run_and_audits():
    project = _project()
    task = _dev_task(project["id"])
    run = client.post(f"/dev-tasks/{task['id']}/aider/prepare", json={}).json()

    res = client.post(
        f"/tool-runs/{run['id']}/aider/record-result",
        json={
            "summary": "applied diff",
            "output": "1 file changed",
            "conclusion": "success",
        },
    )
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["summary"] == "applied diff"
    assert updated["conclusion"] == "success"

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "aider_result_recorded" for e in events)


def test_record_aider_result_rejects_non_aider_run():
    project = _project()
    task = _dev_task(project["id"])
    # Prepare via OpenHands so the ToolRun is runner_type=openhands.
    oh = client.post(
        f"/dev-tasks/{task['id']}/openhands/prepare", json={}
    ).json()
    run_id = oh["tool_run"]["id"]

    res = client.post(
        f"/tool-runs/{run_id}/aider/record-result",
        json={"summary": "s", "output": "o", "conclusion": "success"},
    )
    assert res.status_code == 400
    assert "not an Aider run" in res.text
