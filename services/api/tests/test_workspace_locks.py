"""Concurrency hardening: per-workspace execution mutual exclusion."""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import aider_execution
from app.services.openhands_execution import OpenHandsExecutionResult
from app.services.workspace_locks import (
    WorkspaceBusyError,
    is_locked,
    workspace_execution_lock,
)

client = TestClient(app)


def test_same_workspace_lock_rejects_reentry():
    with workspace_execution_lock("ws-A"):
        assert is_locked("ws-A")
        with pytest.raises(WorkspaceBusyError):
            with workspace_execution_lock("ws-A"):
                pass
    # released on exit
    assert not is_locked("ws-A")
    with workspace_execution_lock("ws-A"):
        pass


def test_different_workspaces_are_independent():
    with workspace_execution_lock("ws-1"):
        with workspace_execution_lock("ws-2"):  # must not block / raise
            assert is_locked("ws-1") and is_locked("ws-2")
    assert not is_locked("ws-1") and not is_locked("ws-2")


def test_lock_released_even_on_exception():
    with pytest.raises(ValueError):
        with workspace_execution_lock("ws-X"):
            raise ValueError("boom")
    assert not is_locked("ws-X")


# --- route-level: a busy workspace yields 409 WORKSPACE_BUSY ---------------

REQ = {"title": "x", "problem_statement": "y"}


@pytest.fixture
def aider_on(monkeypatch, tmp_path):
    root = tmp_path / "wsr"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    monkeypatch.setattr(config, "AIDER_EXECUTION_ENABLED", True)

    class _Stub:
        def run(self, *, argv, cwd, timeout_seconds, max_output_bytes):
            return OpenHandsExecutionResult(
                exit_code=0, stdout="ok", stderr="", timed_out=False,
                duration_seconds=0.01, error=None,
            )

    monkeypatch.setattr(aider_execution, "EXECUTOR", _Stub())
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no subprocess")),
    )


def test_execute_returns_409_when_workspace_busy(aider_on):
    p = client.post("/projects", json={"name": "PL", "description": "d"}).json()
    req = client.post(
        f"/projects/{p['id']}/requirements", json=REQ
    ).json()
    dt = client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()["dev_tasks"][0]
    w = client.post(f"/projects/{p['id']}/workspaces", json={
        "name": "ws", "workspace_type": "local_created",
        "create_directory": True,
    }).json()
    c = client.post("/approvals", json={
        "project_id": p["id"], "target_type": "dev_task",
        "target_id": dt["id"],
    }).json()
    client.patch(f"/approvals/{c['id']}", json={"status": "approved"})

    # Simulate an in-flight execution holding the workspace.
    with workspace_execution_lock(w["id"]):
        r = client.post(
            f"/dev-tasks/{dt['id']}/aider/execute",
            json={"workspace_id": w["id"], "mode": "local"},
        )
        assert r.status_code == 409
        assert "WORKSPACE_BUSY" in r.text

    # Lock released -> the same call now proceeds.
    r2 = client.post(
        f"/dev-tasks/{dt['id']}/aider/execute",
        json={"workspace_id": w["id"], "mode": "local"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "completed"
