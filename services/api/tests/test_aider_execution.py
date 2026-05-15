"""Tests for the real Aider execution bridge.

No real aider / LLM / subprocess — the executor is stubbed and
subprocess.run is blocked. Asserts the OpenHands-equivalent security model
(gate, server-controlled argv, approval, snapshot diff, audit, cost).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import aider_execution
from app.services.openhands_execution import OpenHandsExecutionResult

client = TestClient(app)

REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    return root


@pytest.fixture
def enable_aider(monkeypatch):
    monkeypatch.setattr(config, "AIDER_EXECUTION_ENABLED", True)
    monkeypatch.setattr(config, "AIDER_COMMAND", "aider-fake")
    monkeypatch.setattr(config, "AIDER_TIMEOUT_SECONDS", 60)
    monkeypatch.setattr(config, "AIDER_MAX_OUTPUT_BYTES", 4000)
    monkeypatch.setattr(config, "AIDER_LLM_PROVIDER", "ollama")
    monkeypatch.setattr(config, "AIDER_MODEL", "qwen2.5-coder:3b")


class _StubExec:
    def __init__(self, *, exit_code=0, stdout="ok", stderr="",
                 timed_out=False, error=None, on_run=None):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.error = error
        self.on_run = on_run
        self.calls: list[dict] = []

    def run(self, *, argv, cwd, timeout_seconds, max_output_bytes):
        self.calls.append({"argv": list(argv), "cwd": cwd,
                           "timeout_seconds": timeout_seconds})
        if self.on_run:
            self.on_run(Path(cwd))
        return OpenHandsExecutionResult(
            exit_code=self.exit_code, stdout=self.stdout, stderr=self.stderr,
            timed_out=self.timed_out, duration_seconds=0.01, error=self.error,
        )


def _install(monkeypatch, stub):
    monkeypatch.setattr(aider_execution, "EXECUTOR", stub)
    # Real subprocess must never run in tests.
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("subprocess.run must not run in tests")),
    )
    return stub


def _project():
    return client.post(
        "/projects", json={"name": "PAX", "description": "d"}
    ).json()


def _dev_task(pid):
    req = client.post(
        f"/projects/{pid}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    return client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()["dev_tasks"][0]


def _workspace(pid):
    r = client.post(f"/projects/{pid}/workspaces", json={
        "name": "ws", "workspace_type": "local_created",
        "create_directory": True,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _approve(pid, tid):
    c = client.post("/approvals", json={
        "project_id": pid, "target_type": "dev_task", "target_id": tid,
    }).json()
    client.patch(f"/approvals/{c['id']}", json={"status": "approved"})


# ---------------------------------------------------------------------------


def test_execute_blocked_when_disabled(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "AIDER_EXECUTION_ENABLED", False)
    p = _project(); t = _dev_task(p["id"]); w = _workspace(p["id"])
    _approve(p["id"], t["id"])
    r = client.post(f"/dev-tasks/{t['id']}/aider/execute",
                    json={"workspace_id": w["id"], "mode": "local"})
    assert r.status_code == 409
    assert "AIDER_EXECUTION_DISABLED" in r.text


def test_execute_requires_approval(workspace_root, enable_aider, monkeypatch):
    _install(monkeypatch, _StubExec())
    p = _project(); t = _dev_task(p["id"]); w = _workspace(p["id"])
    # no approval
    r = client.post(f"/dev-tasks/{t['id']}/aider/execute",
                    json={"workspace_id": w["id"], "mode": "local"})
    assert r.status_code == 400


def test_execute_success_records_run_and_cost(
    workspace_root, enable_aider, monkeypatch
):
    def touch(cwd: Path):
        (cwd / "new.py").write_text("x=1\n", encoding="utf-8")

    stub = _install(monkeypatch, _StubExec(exit_code=0, on_run=touch))
    p = _project(); t = _dev_task(p["id"]); w = _workspace(p["id"])
    _approve(p["id"], t["id"])
    r = client.post(f"/dev-tasks/{t['id']}/aider/execute",
                    json={"workspace_id": w["id"], "mode": "local"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["runner_type"] == "aider"
    assert run["status"] == "completed"
    assert run["conclusion"] == "requires_human_action"

    # Server-controlled argv: fixed shape, message via --message-file.
    argv = stub.calls[0]["argv"]
    assert argv[0] == "aider-fake"
    assert "--no-auto-commits" in argv
    assert "--yes" in argv
    assert "--message-file" in argv
    assert "ollama/qwen2.5-coder:3b" in argv

    audit = client.get(f"/projects/{p['id']}/audit-events").json()
    actions = {e["action"] for e in audit}
    assert "aider_execution_requested" in actions
    assert "aider_execution_completed" in actions

    costs = client.get(f"/projects/{p['id']}/cost-records").json()
    aider_c = [c for c in costs if c.get("provider") == "aider"]
    assert len(aider_c) == 1
    assert aider_c[0]["metadata"]["dev_task_id"] == t["id"]


def test_execute_nonzero_exit_marks_failed(
    workspace_root, enable_aider, monkeypatch
):
    _install(monkeypatch, _StubExec(exit_code=2, stderr="boom"))
    p = _project(); t = _dev_task(p["id"]); w = _workspace(p["id"])
    _approve(p["id"], t["id"])
    r = client.post(f"/dev-tasks/{t['id']}/aider/execute",
                    json={"workspace_id": w["id"], "mode": "local"})
    assert r.status_code == 200
    run = r.json()
    assert run["status"] == "failed"
    assert run["conclusion"] == "failure"


def test_execute_rejects_non_local_mode(
    workspace_root, enable_aider, monkeypatch
):
    _install(monkeypatch, _StubExec())
    p = _project(); t = _dev_task(p["id"]); w = _workspace(p["id"])
    _approve(p["id"], t["id"])
    r = client.post(f"/dev-tasks/{t['id']}/aider/execute",
                    json={"workspace_id": w["id"], "mode": "dry_run"})
    assert r.status_code == 400
