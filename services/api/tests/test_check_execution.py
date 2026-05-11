"""Task 35 — Actual Check Execution backend tests.

Verifies CheckDefinitions can be executed through the Safe Command Runner,
producing a linked CheckRun + CommandRun pair with audit + artifact trail.

All subprocess execution is replaced with an injected fake. A separate
``block_real_subprocess`` fixture hard-fails on any unexpected real
``subprocess.run`` / ``os.system`` call to prove no path bypasses the runner.
"""

from __future__ import annotations

import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories_state import audit_event_repo, check_run_repo, command_run_repo
from app.services import command_runner as runner_module

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    return root


@pytest.fixture
def block_real_subprocess(monkeypatch):
    def _fail_run(*args, **kwargs):
        raise AssertionError(
            f"unexpected subprocess.run call: args={args} kwargs={kwargs}"
        )

    def _fail_system(*args, **kwargs):
        raise AssertionError(f"unexpected os.system call: args={args}")

    monkeypatch.setattr(subprocess, "run", _fail_run)
    monkeypatch.setattr(os, "system", _fail_system)


@pytest.fixture
def enable_runner(monkeypatch):
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", True)


REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}


def _make_project(name: str = "QAExec") -> dict:
    resp = client.post("/projects", json={"name": name, "description": "d"})
    assert resp.status_code == 201
    return resp.json()


def _make_repo(project_id: str) -> dict:
    resp = client.post(f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


def _make_workspace(project_id: str, code_repository_id: str | None = None) -> dict:
    payload: dict = {
        "name": "ws",
        "workspace_type": "local_created",
        "create_directory": True,
    }
    if code_repository_id is not None:
        payload["code_repository_id"] = code_repository_id
    resp = client.post(f"/projects/{project_id}/workspaces", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    return body


def _make_check_def(project_id: str, **overrides) -> dict:
    payload = {
        "name": "Backend tests",
        "check_type": "tests",
        "command": "python --version",
        "required": True,
        "enabled": True,
        "severity": "blocking",
    }
    payload.update(overrides)
    resp = client.post(
        f"/projects/{project_id}/check-definitions", json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _install_fake_runner(monkeypatch, fake):
    real_run = runner_module.CommandRunnerService.run

    def wrapped(self, workspace_id, body, *, actor_email, runner=None):
        return real_run(self, workspace_id, body, actor_email=actor_email, runner=fake)

    monkeypatch.setattr(runner_module.CommandRunnerService, "run", wrapped)


def _execute(check_definition_id: str, workspace_id: str, **extra):
    payload = {"workspace_id": workspace_id, "target_type": "manual"}
    payload.update(extra)
    return client.post(
        f"/check-definitions/{check_definition_id}/execute",
        json=payload,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_execute_success_links_command_run_and_artifact(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])

    captured: dict = {}

    def fake(argv, **kwargs):
        captured["argv"] = argv
        captured["shell"] = kwargs.get("shell")
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok\n", stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    check_run = body["check_run"]
    command_run = body["command_run"]

    assert captured["argv"] == ["python", "--version"]
    assert captured["shell"] is False

    assert check_run["status"] == "completed"
    assert check_run["conclusion"] == "success"
    assert check_run["check_definition_id"] == d["id"]
    assert check_run["command_run_id"] == command_run["id"]
    assert check_run["artifact_id"] == command_run["artifact_id"]
    assert check_run["target_type"] == "manual"
    assert check_run["target_id"] == d["id"]

    assert command_run["status"] == "completed"
    assert command_run["conclusion"] == "success"
    assert command_run["exit_code"] == 0
    assert command_run["artifact_id"] is not None


def test_execute_command_parsing_table(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])

    cases = [
        ("pytest", ["pytest"]),
        ("pytest -q", ["pytest", "-q"]),
        ("npm run build", ["npm", "run", "build"]),
        ("python -m pytest", ["python", "-m", "pytest"]),
    ]
    for command, expected_argv in cases:
        d = _make_check_def(project["id"], name=f"def-{command}", command=command)
        captured: dict = {}

        def fake(argv, **kwargs):
            captured["argv"] = argv
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

        _install_fake_runner(monkeypatch, fake)
        resp = _execute(d["id"], ws["id"])
        assert resp.status_code == 201, resp.text
        assert captured["argv"] == expected_argv, (command, captured["argv"])


# ---------------------------------------------------------------------------
# Failure / timeout / blocked mapping
# ---------------------------------------------------------------------------

def test_execute_failure_maps_to_failed(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=2, stdout="", stderr="boom\n")

    _install_fake_runner(monkeypatch, fake)
    resp = _execute(d["id"], ws["id"])
    body = resp.json()
    assert body["check_run"]["status"] == "failed"
    assert body["check_run"]["conclusion"] == "failure"
    assert body["command_run"]["conclusion"] == "failure"
    assert body["command_run"]["exit_code"] == 2


def test_execute_timeout_maps_to_failed(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])

    def fake(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 0))

    _install_fake_runner(monkeypatch, fake)
    resp = _execute(d["id"], ws["id"])
    body = resp.json()
    assert body["check_run"]["status"] == "failed"
    assert body["check_run"]["conclusion"] == "failure"
    assert body["command_run"]["status"] == "timed_out"
    assert body["command_run"]["conclusion"] == "timed_out"
    assert "timed out" in body["check_run"]["summary"].lower()


def test_execute_blocked_command_records_failed_check_with_blocked_command_run(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    # 'git' is on the default blocklist — execution path produces a blocked CommandRun.
    d = _make_check_def(project["id"], command="git status")

    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["check_run"]["status"] == "failed"
    assert body["check_run"]["conclusion"] == "failure"
    assert body["command_run"]["status"] == "blocked"
    assert body["command_run"]["conclusion"] == "blocked"
    assert body["check_run"]["summary"].lower().startswith("blocked")


# ---------------------------------------------------------------------------
# Error / validation cases
# ---------------------------------------------------------------------------

def test_execute_missing_check_definition_returns_404(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = _execute("no-such-def", ws["id"])
    assert resp.status_code == 404


def test_execute_missing_workspace_returns_404(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    d = _make_check_def(project["id"])
    resp = _execute(d["id"], "no-such-workspace")
    assert resp.status_code == 404


def test_execute_project_mismatch_returns_400(
    workspace_root, block_real_subprocess, enable_runner
):
    project_a = _make_project("A")
    project_b = _make_project("B")
    ws_b = _make_workspace(project_b["id"])
    d_a = _make_check_def(project_a["id"])
    resp = _execute(d_a["id"], ws_b["id"])
    assert resp.status_code == 400
    assert "project" in resp.json()["detail"].lower()


def test_execute_repo_mismatch_returns_400(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    repo_one = _make_repo(project["id"])
    # second repo
    resp = client.post(
        f"/projects/{project['id']}/code-repositories",
        json={**REPO_PAYLOAD, "name": "repo2", "repo_url": "https://github.com/org/repo2"},
    )
    assert resp.status_code == 201
    repo_two = resp.json()
    ws = _make_workspace(project["id"], code_repository_id=repo_one["id"])
    d = _make_check_def(project["id"], code_repository_id=repo_two["id"])
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 400
    assert "code repository" in resp.json()["detail"].lower()


def test_execute_disabled_definition_returns_400(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])
    client.patch(f"/check-definitions/{d['id']}", json={"enabled": False})
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 400


def test_execute_empty_command_returns_400(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"], command="")
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "bad_command",
    [
        "pytest && rm -rf /",
        "pytest | tee out",
        "pytest > out",
        "pytest; echo done",
        "echo $(whoami)",
    ],
)
def test_execute_unsafe_command_returns_400(
    bad_command, workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"], command=bad_command)
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 400


def test_execute_returns_403_when_command_runner_disabled(
    workspace_root, block_real_subprocess
):
    # COMMAND_RUNNER_ENABLED defaults to False — do not enable_runner.
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 403
    # nothing recorded since the runner short-circuited
    assert check_run_repo.list_by_project(project["id"]) == []
    assert command_run_repo.list_by_workspace(ws["id"]) == []


# ---------------------------------------------------------------------------
# Audit + safety guarantees
# ---------------------------------------------------------------------------

def test_execute_audit_events_emitted(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok", stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 201
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "check_execution_requested" in actions
    assert "check_execution_completed" in actions


def test_execute_blocked_emits_blocked_audit_event(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"], command="git status")
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 201
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "check_execution_blocked" in actions


def test_execute_no_real_subprocess_when_disabled(workspace_root, block_real_subprocess):
    # block_real_subprocess hard-fails if any code path calls subprocess.run.
    # With COMMAND_RUNNER_ENABLED=false, execute returns 403 without invocation.
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_check_def(project["id"])
    resp = _execute(d["id"], ws["id"])
    assert resp.status_code == 403
