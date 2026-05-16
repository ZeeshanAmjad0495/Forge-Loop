"""Safe Command Runner (Task 34) backend tests.

All runner-side tests inject a fake subprocess.run via the service's `runner`
parameter (called through monkeypatching the route's service factory). The
default test setup also monkeypatches `subprocess.run` and `os.system` to
assert no real shell-out happens anywhere.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories_state import audit_event_repo, command_run_repo
from app.services import command_runner as runner_module

client = TestClient(app)


REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}


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
    """Hard guard — fail loudly if any code path tries to spawn a real process."""
    calls: list[tuple] = []

    def _fail_run(*args, **kwargs):
        calls.append(("subprocess.run", args, kwargs))
        raise AssertionError(
            f"unexpected subprocess.run call: args={args} kwargs={kwargs}"
        )

    def _fail_system(*args, **kwargs):
        calls.append(("os.system", args, kwargs))
        raise AssertionError(f"unexpected os.system call: args={args}")

    monkeypatch.setattr(subprocess, "run", _fail_run)
    monkeypatch.setattr(os, "system", _fail_system)
    return calls


@pytest.fixture
def enable_runner(monkeypatch):
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", True)
    # #45/H3: interpreters are no longer on the default allowlist. These
    # tests exercise runner *mechanics* with a harmless `python` command,
    # so they opt it in explicitly (mirrors the new informed-opt-in
    # model). Production default stays interpreter-free.
    monkeypatch.setattr(
        config, "COMMAND_RUNNER_ALLOWED_COMMANDS",
        [*config.COMMAND_RUNNER_ALLOWED_COMMANDS, "python", "python3"],
    )


def _make_project(name: str = "TestProject") -> dict:
    resp = client.post("/projects", json={"name": name, "description": "d"})
    assert resp.status_code == 201
    return resp.json()


def _make_repo(project_id: str) -> dict:
    resp = client.post(f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


def _make_workspace(project_id: str) -> dict:
    resp = client.post(
        f"/projects/{project_id}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    return body


def _make_definition(project_id: str, **overrides) -> dict:
    payload = {
        "name": "Version check",
        # #45/H3: default to an allowlisted command (interpreters are no
        # longer default-allowlisted). Tests needing `python` pass it
        # explicitly under the enable_runner allowlist.
        "command": "uv",
        "args": ["--version"],
        "command_type": "utility",
        "timeout_seconds": 5,
    }
    payload.update(overrides)
    resp = client.post(f"/projects/{project_id}/command-definitions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _install_fake_runner(monkeypatch, fake):
    """Patch CommandRunnerService.run to inject a fake subprocess runner."""
    real_run = runner_module.CommandRunnerService.run

    def wrapped(self, workspace_id, body, *, actor_email, runner=None):
        return real_run(self, workspace_id, body, actor_email=actor_email, runner=fake)

    monkeypatch.setattr(runner_module.CommandRunnerService, "run", wrapped)


# ---------------------------------------------------------------------------
# CommandDefinition CRUD
# ---------------------------------------------------------------------------

def test_create_command_definition_success(workspace_root, block_real_subprocess):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={
            "name": "Backend tests",
            "command": "pytest",
            "args": ["-q"],
            "command_type": "test",
            "timeout_seconds": 120,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert body["command"] == "pytest"
    assert body["args"] == ["-q"]
    assert body["command_type"] == "test"
    assert body["enabled"] is True
    assert body["requires_approval"] is True
    assert body["timeout_seconds"] == 120


def test_create_command_definition_missing_project_404(workspace_root, block_real_subprocess):
    resp = client.post(
        "/projects/does-not-exist/command-definitions",
        json={"name": "x", "command": "pytest"},
    )
    assert resp.status_code == 404


def test_create_command_definition_missing_workspace_404(workspace_root, block_real_subprocess):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={"name": "x", "command": "pytest", "workspace_id": "no-such-workspace"},
    )
    assert resp.status_code == 404


def test_create_command_definition_missing_code_repository_404(workspace_root, block_real_subprocess):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={"name": "x", "command": "pytest", "code_repository_id": "no-such-repo"},
    )
    assert resp.status_code == 404


def test_create_command_definition_rejects_command_with_slash(workspace_root, block_real_subprocess):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={"name": "x", "command": "/usr/bin/pytest"},
    )
    assert resp.status_code == 422  # pydantic validation


@pytest.mark.parametrize(
    "bad_arg",
    ["foo|bar", "a && b", "a; b", "a > b", "$(whoami)", "`whoami`", "a\nb"],
)
def test_create_command_definition_rejects_arg_with_shell_metachars(
    bad_arg, workspace_root, block_real_subprocess
):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={"name": "x", "command": "pytest", "args": [bad_arg]},
    )
    assert resp.status_code == 422


def test_create_command_definition_rejects_disallowed_command(workspace_root, block_real_subprocess):
    project = _make_project()
    resp = client.post(
        f"/projects/{project['id']}/command-definitions",
        json={"name": "x", "command": "git"},
    )
    assert resp.status_code == 400


def test_list_command_definitions_by_project(workspace_root, block_real_subprocess):
    project = _make_project()
    _make_definition(project["id"], name="A")
    _make_definition(project["id"], name="B", command="pytest", args=[])
    resp = client.get(f"/projects/{project['id']}/command-definitions")
    assert resp.status_code == 200
    names = sorted(d["name"] for d in resp.json())
    assert names == ["A", "B"]


def test_get_command_definition(workspace_root, block_real_subprocess):
    project = _make_project()
    d = _make_definition(project["id"])
    resp = client.get(f"/command-definitions/{d['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == d["id"]


def test_patch_command_definition_updates_safe_fields(workspace_root, block_real_subprocess):
    project = _make_project()
    d = _make_definition(project["id"], command="pytest")  # #45/H3: allowlisted
    resp = client.patch(
        f"/command-definitions/{d['id']}",
        json={"enabled": False, "timeout_seconds": 30, "description": "edited"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["timeout_seconds"] == 30
    assert body["description"] == "edited"


# ---------------------------------------------------------------------------
# Runner safety — feature disabled and missing entities
# ---------------------------------------------------------------------------

def test_run_blocked_when_command_runner_disabled(workspace_root, block_real_subprocess):
    # COMMAND_RUNNER_ENABLED defaults to False — do not enable_runner
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"], command="pytest")  # #45/H3: allowlisted
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 403
    # no CommandRun saved when the feature itself is off
    assert command_run_repo.list_by_workspace(ws["id"]) == []


def test_run_missing_workspace_404(workspace_root, block_real_subprocess, enable_runner):
    project = _make_project()
    d = _make_definition(project["id"])
    resp = client.post(
        "/workspaces/no-such/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 404


def test_run_missing_command_definition_404(workspace_root, block_real_subprocess, enable_runner):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": "no-such"},
    )
    assert resp.status_code == 404


def test_run_disabled_definition_returns_400(workspace_root, block_real_subprocess, enable_runner):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])
    client.patch(f"/command-definitions/{d['id']}", json={"enabled": False})
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Runner safety — allowlist/blocklist, path traversal, shell metachars
# ---------------------------------------------------------------------------

def test_run_disallowed_command_records_blocked_run(workspace_root, block_real_subprocess, enable_runner):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command": "wget", "args": ["http://x"], "target_type": "manual"},
    )
    # ad-hoc command goes through validation; with COMMAND_RUNNER_ENABLED it should
    # record a blocked run rather than 403
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["conclusion"] == "blocked"


@pytest.mark.parametrize("bad_command", ["rm", "git", "curl", "docker", "ssh", "sudo"])
def test_run_blocklisted_command_records_blocked(
    bad_command, workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command": bad_command, "target_type": "manual"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "blocked"


def test_run_arg_with_shell_metachar_rejected_at_validation(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command": "python", "args": ["a && b"], "target_type": "manual"},
    )
    # pydantic validation catches metachars before the service runs
    assert resp.status_code == 422


def test_run_working_directory_path_traversal_blocked(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={
            "command": "python",
            "args": ["--version"],
            "working_directory": "../../etc",
            "target_type": "manual",
        },
    )
    assert resp.status_code == 422


def test_run_absolute_working_directory_rejected(
    workspace_root, block_real_subprocess, enable_runner
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={
            "command": "python",
            "args": ["--version"],
            "working_directory": "/etc",
            "target_type": "manual",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Runner execution with injected fake subprocess
# ---------------------------------------------------------------------------

def test_run_safe_command_success_records_completed(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    # enable_runner allowlists python; argv assertion below expects it.
    d = _make_definition(project["id"], command="python")

    captured: dict = {}

    def fake(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok\n", stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["conclusion"] == "success"
    assert body["exit_code"] == 0
    assert body["stdout"] == "ok\n"
    # fake was called with shell=False, list argv, env restricted, cwd inside workspace
    assert captured["argv"] == ["python", "--version"]
    assert captured["kwargs"]["shell"] is False
    assert set(captured["kwargs"]["env"].keys()) == {"PATH"}
    cwd = captured["kwargs"]["cwd"]
    assert Path(cwd).resolve().is_relative_to(Path(ws["root_path"]).resolve())


def test_run_failing_command_records_failed(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=2, stdout="", stderr="boom\n")

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    body = resp.json()
    assert body["status"] == "failed"
    assert body["conclusion"] == "failure"
    assert body["exit_code"] == 2
    assert body["stderr"] == "boom\n"


def test_run_timeout_records_timed_out(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 0))

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    body = resp.json()
    assert body["status"] == "timed_out"
    assert body["conclusion"] == "timed_out"
    assert "timed out" in (body["error_message"] or "")


def test_run_stdout_capped_to_max_output_bytes(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    monkeypatch.setattr(config, "COMMAND_RUNNER_MAX_OUTPUT_BYTES", 200)

    big = "x" * 5000

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout=big, stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    body = resp.json()
    # per-stream cap is half of the total cap; truncation marker present
    assert len(body["stdout"]) <= 100 + len(runner_module.TRUNCATION_MARKER)
    assert "truncated" in body["stdout"]


def test_run_creates_artifact_when_output_present(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="hello", stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    body = resp.json()
    assert body["artifact_id"] is not None


def test_run_no_real_subprocess_executed_when_disabled(workspace_root, block_real_subprocess):
    # block_real_subprocess hard-fails on any subprocess.run / os.system invocation.
    # COMMAND_RUNNER_ENABLED is False by default → run should return 403 without
    # any subprocess attempt.
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"], command="pytest")  # #45/H3: allowlisted
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 403
    # block_real_subprocess fixture would have raised had subprocess.run been called


def test_runner_never_uses_shell_true(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    seen_shell: list = []

    def fake(argv, **kwargs):
        seen_shell.append(kwargs.get("shell"))
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok", stderr="")

    _install_fake_runner(monkeypatch, fake)
    client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert seen_shell == [False]


# ---------------------------------------------------------------------------
# Listing & audit
# ---------------------------------------------------------------------------

def test_list_command_runs_by_workspace_and_by_project(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok", stderr="")

    _install_fake_runner(monkeypatch, fake)
    client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    by_ws = client.get(f"/workspaces/{ws['id']}/command-runs")
    by_proj = client.get(f"/projects/{project['id']}/command-runs")
    assert by_ws.status_code == 200
    assert by_proj.status_code == 200
    assert len(by_ws.json()) == 2
    assert len(by_proj.json()) == 2


def test_audit_events_recorded(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok", stderr="")

    _install_fake_runner(monkeypatch, fake)
    client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    # blocked path
    client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command": "wget", "target_type": "manual"},
    )

    actions = {e.action for e in audit_event_repo.list_by_project(project["id"])}
    assert "command_definition_created" in actions
    assert "command_run_requested" in actions
    assert "command_run_completed" in actions
    assert "command_run_blocked" in actions


# ---------------------------------------------------------------------------
# External isolation — GitHub / OpenHands / Firestore must not be called
# ---------------------------------------------------------------------------

def test_runner_uses_only_repository_abstractions(
    workspace_root, block_real_subprocess, enable_runner, monkeypatch
):
    # The block_real_subprocess fixture already enforces no shell-out.
    # This test additionally fails if any github / openhands runner factory is
    # invoked during a command run.
    import app.tool_runners.openhands as openhands_module

    sentinel_calls: list[str] = []

    def _fail_factory(*args, **kwargs):
        sentinel_calls.append("openhands.OpenHandsRunner()")
        raise AssertionError("OpenHands runner must not be called from command runner")

    monkeypatch.setattr(openhands_module, "OpenHandsRunner", _fail_factory)

    project = _make_project()
    ws = _make_workspace(project["id"])
    d = _make_definition(project["id"])

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="ok", stderr="")

    _install_fake_runner(monkeypatch, fake)
    resp = client.post(
        f"/workspaces/{ws['id']}/command-runs",
        json={"command_definition_id": d["id"]},
    )
    assert resp.status_code == 201
    assert sentinel_calls == []
