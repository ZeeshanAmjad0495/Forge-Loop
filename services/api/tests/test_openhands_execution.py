"""Tests for OpenHands controlled local execution mode (Task 36).

Uses a fake OpenHandsExecutor injected at the module-level singleton so that
no real OpenHands binary, subprocess, git, GitHub, network, or LLM is invoked.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import openhands_execution
from app.services.openhands_execution import OpenHandsExecutionResult


client = TestClient(app)


REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    return root


@pytest.fixture
def enable_execution(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(config, "OPENHANDS_COMMAND", "openhands-fake")
    monkeypatch.setattr(config, "OPENHANDS_ALLOWED_ARGS", [])
    monkeypatch.setattr(config, "OPENHANDS_TIMEOUT_SECONDS", 60)
    monkeypatch.setattr(config, "OPENHANDS_MAX_OUTPUT_BYTES", 4000)


class _RecordingExecutor:
    def __init__(self, *, exit_code=0, stdout="", stderr="", timed_out=False,
                 error=None, on_run=None, duration_seconds=0.01):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.error = error
        self.on_run = on_run
        self.duration_seconds = duration_seconds
        self.calls: list[dict] = []

    def run(self, *, command, args, cwd, timeout_seconds, max_output_bytes,
            working_directory=None, title=None):
        self.calls.append({
            "command": command,
            "args": list(args),
            "cwd": cwd,
            "timeout_seconds": timeout_seconds,
            "max_output_bytes": max_output_bytes,
            "working_directory": working_directory,
            "title": title,
        })
        if self.on_run is not None:
            self.on_run(Path(cwd))
        return OpenHandsExecutionResult(
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
            timed_out=self.timed_out,
            duration_seconds=self.duration_seconds,
            error=self.error,
        )


def _install_executor(monkeypatch, executor) -> _RecordingExecutor:
    monkeypatch.setattr(openhands_execution, "EXECUTOR", executor)
    return executor


def _block_real_subprocess(monkeypatch):
    def fake_run(*args, **kwargs):
        raise AssertionError(f"subprocess.run must not be invoked in tests: {args}")

    def fake_system(*args, **kwargs):
        raise AssertionError(f"os.system must not be invoked in tests: {args}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)


def _create_project(name: str = "P36") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_dev_task(project_id: str) -> dict:
    req = client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return decomp["dev_tasks"][0]


def _create_workspace(project_id: str, *, status_ready: bool = True) -> dict:
    body = {
        "name": "ws",
        "workspace_type": "local_created",
        "create_directory": True,
    }
    res = client.post(f"/projects/{project_id}/workspaces", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _approve(project_id: str, target_type: str, target_id: str) -> dict:
    created = client.post("/approvals", json={
        "project_id": project_id,
        "target_type": target_type,
        "target_id": target_id,
    }).json()
    decided = client.patch(
        f"/approvals/{created['id']}", json={"status": "approved"}
    ).json()
    return decided


# ---------------------------------------------------------------------------
# Disabled / config gating
# ---------------------------------------------------------------------------


def test_local_execution_returns_409_when_disabled(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", False)
    monkeypatch.setattr(config, "OPENHANDS_COMMAND", "")
    fake = _install_executor(monkeypatch, _RecordingExecutor())

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 409
    assert "OPENHANDS_EXECUTION_DISABLED" in res.text
    assert fake.calls == []


def test_local_execution_returns_409_when_command_unset(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(config, "OPENHANDS_COMMAND", "")
    fake = _install_executor(monkeypatch, _RecordingExecutor())

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 409
    assert "OPENHANDS_COMMAND_NOT_CONFIGURED" in res.text
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


def test_dry_run_returns_prepared_shape_and_does_not_invoke_executor(
    workspace_root, monkeypatch
):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", False)
    fake = _install_executor(monkeypatch, _RecordingExecutor())

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "dry_run"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["tool_run"]["mode"] == "dry_run"
    assert data["tool_run"]["status"] == "completed"
    assert data["execution_summary"]["mode"] == "dry_run"
    assert data["instruction_package"]["runner"] == "openhands"
    assert fake.calls == []

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "openhands_package_prepared" in actions


# ---------------------------------------------------------------------------
# 404 / 400 validation
# ---------------------------------------------------------------------------


def test_execute_unknown_dev_task_returns_404(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor())
    res = client.post(
        "/dev-tasks/missing/openhands/execute",
        json={"workspace_id": "irrelevant", "mode": "local"},
    )
    assert res.status_code == 404


def test_execute_unknown_workspace_returns_404(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor())
    project = _create_project()
    task = _create_dev_task(project["id"])
    _approve(project["id"], "dev_task", task["id"])
    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": "missing", "mode": "local"},
    )
    assert res.status_code == 404


def test_execute_workspace_project_mismatch_rejected(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor())
    project_a = _create_project("A")
    project_b = _create_project("B")
    task_a = _create_dev_task(project_a["id"])
    ws_b = _create_workspace(project_b["id"])
    _approve(project_a["id"], "dev_task", task_a["id"])

    res = client.post(
        f"/dev-tasks/{task_a['id']}/openhands/execute",
        json={"workspace_id": ws_b["id"], "mode": "local"},
    )
    assert res.status_code == 400
    assert "does not belong" in res.text


def test_execute_rejects_workspace_not_ready(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor())
    project = _create_project()
    task = _create_dev_task(project["id"])
    # workspace with create_directory=false stays "registered", not "ready"
    res_ws = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    )
    ws = res_ws.json()
    assert ws["status"] == "registered"
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 400
    assert "not ready" in res.text


# ---------------------------------------------------------------------------
# Approval gating
# ---------------------------------------------------------------------------


def test_execute_requires_approval_when_none_provided(workspace_root, enable_execution, monkeypatch):
    fake = _install_executor(monkeypatch, _RecordingExecutor())
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 400
    assert "approval" in res.text.lower()
    assert fake.calls == []


def test_execute_with_approved_dev_task_approval_proceeds(
    workspace_root, enable_execution, monkeypatch
):
    fake = _install_executor(monkeypatch, _RecordingExecutor(exit_code=0))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    assert len(fake.calls) == 1


def test_execute_with_approved_task_decomposition_approval_proceeds(
    workspace_root, enable_execution, monkeypatch
):
    fake = _install_executor(monkeypatch, _RecordingExecutor(exit_code=0))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "task_decomposition", task["agent_run_id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    assert len(fake.calls) == 1


def test_execute_with_explicit_approval_id_validates_match(
    workspace_root, enable_execution, monkeypatch
):
    _install_executor(monkeypatch, _RecordingExecutor())
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    appr = _approve(project["id"], "dev_task", "some-other-target")

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={
            "workspace_id": ws["id"],
            "mode": "local",
            "approval_id": appr["id"],
        },
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Executor contract
# ---------------------------------------------------------------------------


def test_executor_called_with_workspace_root_cwd_and_no_shell(
    workspace_root, enable_execution, monkeypatch
):
    fake = _install_executor(monkeypatch, _RecordingExecutor())
    _block_real_subprocess(monkeypatch)

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["command"] == "openhands-fake"
    assert call["cwd"] == str(Path(ws["root_path"]).resolve())
    assert isinstance(call["args"], list)
    assert call["timeout_seconds"] == 60


def test_executor_argv_built_from_allowed_args_template(
    workspace_root, enable_execution, monkeypatch
):
    monkeypatch.setattr(config, "OPENHANDS_ALLOWED_ARGS", ["--instruction-file", "{instruction_file}"])
    fake = _install_executor(monkeypatch, _RecordingExecutor())

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    args = fake.calls[0]["args"]
    assert args[0] == "--instruction-file"
    instr_path = Path(args[1])
    assert instr_path.is_absolute()
    assert instr_path.exists()
    assert instr_path.is_relative_to(Path(ws["root_path"]).resolve() / ".forgeloop")


def test_timeout_capped_by_hard_cap(workspace_root, enable_execution, monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_HARD_CAP_SECONDS", 5)
    fake = _install_executor(monkeypatch, _RecordingExecutor())

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local", "timeout_seconds": 9999},
    )
    assert res.status_code == 200
    assert fake.calls[0]["timeout_seconds"] == 5


# ---------------------------------------------------------------------------
# Outcome mapping
# ---------------------------------------------------------------------------


def test_exit_zero_creates_completed_requires_human_action_run(
    workspace_root, enable_execution, monkeypatch
):
    def touch(cwd: Path) -> None:
        (cwd / "new_file.txt").write_text("hello", encoding="utf-8")

    _install_executor(monkeypatch, _RecordingExecutor(
        exit_code=0, stdout="ok\n", on_run=touch
    ))

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    run = data["tool_run"]
    assert run["status"] == "completed"
    assert run["conclusion"] == "requires_human_action"
    assert run["mode"] == "local"
    summary = data["execution_summary"]
    assert summary["exit_code"] == 0
    assert any(c["path"] == "new_file.txt" and c["change_type"] == "added"
               for c in summary["changed_paths"])

    actions = [e["action"] for e in client.get(
        f"/projects/{project['id']}/audit-events"
    ).json()]
    assert "openhands_execution_requested" in actions
    assert "openhands_execution_started" in actions
    assert "openhands_execution_completed" in actions

    # C2 follow-up: the execution emits a CostRecord (-> Langfuse trace).
    costs = client.get(
        f"/projects/{project['id']}/cost-records"
    ).json()
    oh_costs = [c for c in costs if c["source_type"] == "tool_run"
                and c["provider"] == "openhands"]
    assert len(oh_costs) == 1
    assert oh_costs[0]["source_id"] == run["id"]
    assert oh_costs[0]["metadata"]["dev_task_id"] == task["id"]
    assert "resolve_seconds" in oh_costs[0]["metadata"]


def test_nonzero_exit_creates_failed_run(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor(
        exit_code=2, stderr="boom\n"
    ))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200
    run = res.json()["tool_run"]
    assert run["status"] == "failed"
    assert run["conclusion"] == "failure"
    actions = [e["action"] for e in client.get(
        f"/projects/{project['id']}/audit-events"
    ).json()]
    assert "openhands_execution_failed" in actions


def test_timeout_creates_failed_run_with_timed_out_audit(
    workspace_root, enable_execution, monkeypatch
):
    _install_executor(monkeypatch, _RecordingExecutor(
        exit_code=None, timed_out=True, error="timed out after 60s"
    ))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200
    data = res.json()
    run = data["tool_run"]
    assert run["status"] == "failed"
    assert run["conclusion"] == "failure"
    assert "TIMED OUT" in run["summary"]
    assert data["execution_summary"]["timed_out"] is True
    actions = [e["action"] for e in client.get(
        f"/projects/{project['id']}/audit-events"
    ).json()]
    assert "openhands_execution_timed_out" in actions


def test_output_is_capped(workspace_root, enable_execution, monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_MAX_OUTPUT_BYTES", 200)
    big = "A" * 5000
    _install_executor(monkeypatch, _RecordingExecutor(
        exit_code=0, stdout=big, stderr=big
    ))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200
    output = res.json()["tool_run"]["output"] or ""
    assert len(output) <= 200
    assert "...[truncated]" in output


# ---------------------------------------------------------------------------
# Workspace evidence (no git)
# ---------------------------------------------------------------------------


def test_changed_paths_summary_includes_added_modified_deleted(
    workspace_root, enable_execution, monkeypatch
):
    # Pre-seed a file so we can both modify and delete it via the fake executor.
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    ws_path = Path(ws["root_path"]).resolve()
    (ws_path / "to_modify.txt").write_text("original", encoding="utf-8")
    (ws_path / "to_delete.txt").write_text("bye", encoding="utf-8")
    time.sleep(0.01)  # ensure mtime differs

    def mutate(cwd: Path) -> None:
        (cwd / "to_modify.txt").write_text("changed!", encoding="utf-8")
        (cwd / "to_delete.txt").unlink()
        (cwd / "new.txt").write_text("hi", encoding="utf-8")

    _install_executor(monkeypatch, _RecordingExecutor(exit_code=0, on_run=mutate))
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    summary = res.json()["execution_summary"]
    by_type = {c["path"]: c["change_type"] for c in summary["changed_paths"]}
    assert by_type.get("new.txt") == "added"
    assert by_type.get("to_modify.txt") == "modified"
    assert by_type.get("to_delete.txt") == "deleted"


def test_blocked_path_change_marks_run_requires_human_action(
    workspace_root, enable_execution, monkeypatch
):
    project = client.post("/projects", json={"name": "P36b", "description": "d"}).json()
    repo = client.post(
        f"/projects/{project['id']}/code-repositories",
        json={
            "provider": "github",
            "repo_url": "https://github.com/org/repo",
            "name": "repo",
            "default_branch": "main",
        },
    ).json()
    client.post(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": ["secrets"],
            "required_checks": [],
            "requires_approval_for": [],
            "protected_branches": [],
            "notes": "",
        },
    )
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    task = decomp["dev_tasks"][0]
    # Create workspace pinned to that repo so safety profile applies.
    ws = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_created",
            "create_directory": True,
            "code_repository_id": repo["id"],
        },
    ).json()
    _approve(project["id"], "dev_task", task["id"])

    def write_blocked(cwd: Path) -> None:
        (cwd / "secrets").mkdir(exist_ok=True)
        (cwd / "secrets" / "creds.txt").write_text("k=v", encoding="utf-8")

    _install_executor(monkeypatch, _RecordingExecutor(exit_code=0, on_run=write_blocked))

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    run = data["tool_run"]
    assert run["status"] == "failed"
    assert run["conclusion"] == "requires_human_action"
    assert data["execution_summary"]["blocked_path_changes"]
    actions = [e["action"] for e in client.get(
        f"/projects/{project['id']}/audit-events"
    ).json()]
    assert "openhands_execution_blocked" in actions


# ---------------------------------------------------------------------------
# Artifacts and audit
# ---------------------------------------------------------------------------


def test_execution_creates_three_artifact_types(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor(
        exit_code=0, stdout="hello", stderr="warn"
    ))
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200, res.text
    from app.main import artifact_repo

    # Artifact repo doesn't have a list helper here, but we can verify the
    # tool_run.artifact_id points at the changed-paths artifact.
    run_id = res.json()["tool_run"]["id"]
    fetched = client.get(f"/tool-runs/{run_id}").json()
    assert fetched["artifact_id"]
    artifact = artifact_repo.get(fetched["artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type == "openhands_execution_changed_paths"


# ---------------------------------------------------------------------------
# No external side effects
# ---------------------------------------------------------------------------


def test_no_real_subprocess_invoked_anywhere(workspace_root, enable_execution, monkeypatch):
    _install_executor(monkeypatch, _RecordingExecutor(exit_code=0))
    _block_real_subprocess(monkeypatch)

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"])
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/dev-tasks/{task['id']}/openhands/execute",
        json={"workspace_id": ws["id"], "mode": "local"},
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# B1: pre-execute sandbox sync (sync_workspace_to_branch_head)
# ---------------------------------------------------------------------------

import shutil  # noqa: E402

from app.services.openhands_execution import (  # noqa: E402
    SandboxSyncError,
    sync_workspace_to_branch_head,
)

GIT = shutil.which("git")
requires_git = pytest.mark.skipif(GIT is None, reason="git not available")


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.name", "t"], check=True)
    (p / "main.py").write_text("print('v1')\n")
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(p), "-c", "commit.gpgsign=false",
                     "commit", "-q", "-m", "init"], check=True)


@requires_git
def test_sync_noop_when_not_git(tmp_path):
    assert sync_workspace_to_branch_head(tmp_path) is None


@requires_git
def test_sync_refuses_protected_branch(tmp_path):
    _init_repo(tmp_path)  # default branch (main/master) is protected
    with pytest.raises(SandboxSyncError):
        sync_workspace_to_branch_head(tmp_path)


@requires_git
def test_sync_discards_bled_state_on_forgeloop_branch(tmp_path):
    _init_repo(tmp_path)
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-c",
                    "forgeloop/dev-task/x"], check=True)
    # Simulate bleed: a tracked-modified file + an untracked stray file.
    (tmp_path / "main.py").write_text("BLED tracked change\n")
    (tmp_path / "stray.py").write_text("bled untracked\n")
    branch = sync_workspace_to_branch_head(tmp_path)
    assert branch == "forgeloop/dev-task/x"
    assert (tmp_path / "main.py").read_text() == "print('v1')\n"   # reverted
    assert not (tmp_path / "stray.py").exists()                     # cleaned


@requires_git
def test_sync_preserves_gitignored_artifacts(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text(".venv/\n.coverage\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "commit.gpgsign=false",
                    "commit", "-q", "-m", "gi"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-c",
                    "forgeloop/dev-task/y"], check=True)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x").write_text("cached")
    (tmp_path / ".coverage").write_text("cov")
    sync_workspace_to_branch_head(tmp_path)
    # -fd (not -x): gitignored caches survive for speed.
    assert (tmp_path / ".venv" / "x").exists()
    assert (tmp_path / ".coverage").exists()


@requires_git
def test_sync_removes_bled_disposable_db(tmp_path):
    # #44 finding: a gitignored migration-stamped SQLite DB bleeds across
    # dev-task branches -> spurious alembic QA failures. B1 sync must drop
    # disposable dev DBs while still keeping caches.
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("*.db\n.coverage\n.venv/\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "commit.gpgsign=false",
                     "commit", "-q", "-m", "gi"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-c",
                     "forgeloop/dev-task/z"], check=True)
    (tmp_path / "probepilot.db").write_text("stale-alembic-stamp")
    sub = tmp_path / "app"
    sub.mkdir()
    (sub / "test.sqlite3").write_text("nested stamped db")
    (tmp_path / ".coverage").write_text("cov")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x").write_text("cached")

    sync_workspace_to_branch_head(tmp_path)

    assert not (tmp_path / "probepilot.db").exists()      # removed
    assert not (sub / "test.sqlite3").exists()            # nested removed
    assert (tmp_path / ".coverage").exists()              # cache kept
    assert (tmp_path / ".venv" / "x").exists()            # venv kept
