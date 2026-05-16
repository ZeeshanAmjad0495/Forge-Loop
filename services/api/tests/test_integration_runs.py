"""Tests for B2: native multi-dev-task integration.

Uses real temp git repositories — no remotes, no network. The core guarantee
under test: every requested source branch is accounted for, and a merge
conflict surfaces as a structured 409 (no member is ever silently dropped).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)

GIT_BIN = shutil.which("git")
requires_git = pytest.mark.skipif(GIT_BIN is None, reason="git CLI not available")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            GIT_BIN,
            "-c", "init.defaultBranch=main",
            "-c", "user.name=Test",
            "-c", "user.email=test@local",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(path: Path) -> None:
    assert _git(path, "init").returncode == 0
    assert _git(path, "commit", "--allow-empty", "-m", "init").returncode == 0


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    if GIT_BIN:
        monkeypatch.setattr(config, "GIT_BINARY", GIT_BIN)
    return root


@pytest.fixture
def enable_git_workflow(monkeypatch):
    monkeypatch.setattr(config, "GIT_WORKFLOW_ENABLED", True)


def _create_project(name: str = "PB2") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_git_workspace(project_id: str, root: Path) -> dict:
    ws_dir = root / "ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    _init_repo(ws_dir)
    res = client.post(
        f"/projects/{project_id}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(ws_dir),
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _branch_with_commit(
    ws: dict, name: str, filename: str, content: str
) -> str:
    """Create a forgeloop branch via the API, then commit a file on it.

    Returns the WorkspaceBranch id. Leaves the branch with one commit on
    top of main; status stays 'clean' (accepted by the integration run).
    """
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"name": name, "base_branch": "main"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["workspace_branch"]["name"] == name
    root = Path(ws["root_path"])
    (root / filename).write_text(content, encoding="utf-8")
    assert _git(root, "add", filename).returncode == 0
    assert _git(root, "commit", "-m", f"add {filename}").returncode == 0
    return body["workspace_branch"]["id"]


@requires_git
def test_integration_run_merges_all_members(workspace_root, enable_git_workflow):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    b2 = _branch_with_commit(ws, "forgeloop/dev-task/dt2", "b.txt", "beta\n")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1, b2], "base_branch": "main"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "integrated"
    assert [m["status"] for m in data["members"]] == ["merged", "merged"]
    assert data["commit_sha"]
    assert data["git_commit_record_id"]

    integ = data["integration_branch"]["name"]
    root = Path(ws["root_path"])
    assert _git(root, "switch", integ).returncode == 0
    assert (root / "a.txt").read_text() == "alpha\n"
    assert (root / "b.txt").read_text() == "beta\n"


@requires_git
def test_integration_run_conflict_surfaces_409_no_silent_drop(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "shared.txt", "A\n")
    b2 = _branch_with_commit(ws, "forgeloop/dev-task/dt2", "shared.txt", "B\n")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1, b2], "base_branch": "main"},
    )
    assert res.status_code == 409, res.text
    detail = res.json()["detail"]
    assert detail["error"] == "INTEGRATION_CONFLICT"
    members = detail["members"]
    # Every member is explicitly accounted for — none dropped.
    assert len(members) == 2
    assert members[0]["status"] == "merged"
    assert members[1]["status"] == "conflict"
    assert "shared.txt" in members[1]["conflicting_files"]

    # The integration WorkspaceBranch is recorded as failed (not lost).
    branches = client.get(
        f"/workspaces/{ws['id']}/branches"
    ).json()
    integ = [b for b in branches if b["name"].startswith("forgeloop/integration/")]
    assert len(integ) == 1
    assert integ[0]["status"] == "failed"

    # Conflict was aborted cleanly — workspace is not left mid-merge.
    root = Path(ws["root_path"])
    status = _git(root, "status", "--porcelain=v1")
    assert "UU " not in status.stdout


@requires_git
def test_integration_run_rejects_unknown_branch_id(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1, "does-not-exist"]},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["error"] == "INVALID_SOURCE_BRANCHES"


@requires_git
def test_integration_run_rejects_duplicates(workspace_root, enable_git_workflow):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1, b1]},
    )
    assert res.status_code == 400, res.text
    assert "duplicate" in res.text.lower()


@requires_git
def test_integration_run_409_when_git_workflow_disabled(
    workspace_root, monkeypatch
):
    monkeypatch.setattr(config, "GIT_WORKFLOW_ENABLED", False)
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": ["x"]},
    )
    assert res.status_code == 409
    assert "GIT_WORKFLOW_DISABLED" in res.text


@requires_git
def test_integration_run_dirty_workspace_409(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    b2 = _branch_with_commit(ws, "forgeloop/dev-task/dt2", "b.txt", "beta\n")
    # Leave an uncommitted file in the working tree.
    (Path(ws["root_path"]) / "dirty.txt").write_text("x", encoding="utf-8")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1, b2], "base_branch": "main"},
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["error"] == "WORKSPACE_DIRTY"


@requires_git
def test_integration_run_creates_pr_draft(workspace_root, enable_git_workflow):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    b2 = _branch_with_commit(ws, "forgeloop/dev-task/dt2", "b.txt", "beta\n")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={
            "source_branch_ids": [b1, b2],
            "base_branch": "main",
            "create_pr_draft": True,
            "code_repository_id": "repo-xyz",
            "target_branch": "main",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "integrated"
    assert data["pr_draft_id"]
    assert data["notes"] == []


# --- (b) B2 stale-base hardening -----------------------------------------


def _advance_origin_main(root: Path, extra_file: str) -> str:
    """Simulate origin/main moving AHEAD of local main without network:
    commit on main, point refs/remotes/origin/main at it, reset main back.
    """
    a = _git(root, "rev-parse", "main").stdout.strip()
    assert _git(root, "switch", "main").returncode == 0
    (root / extra_file).write_text("from remote\n", encoding="utf-8")
    _git(root, "add", extra_file)
    assert _git(root, "commit", "-m", "remote advance").returncode == 0
    b = _git(root, "rev-parse", "main").stdout.strip()
    assert _git(root, "update-ref", "refs/remotes/origin/main", b).returncode == 0
    assert _git(root, "reset", "--hard", a).returncode == 0
    return b


@requires_git
def test_b2_detects_stale_base_and_warns(workspace_root, enable_git_workflow):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    _advance_origin_main(Path(ws["root_path"]), "remote_only.txt")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1], "base_branch": "main"},
    )
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["status"] == "integrated"
    assert d["base_is_current"] is False
    assert d["base_upstream"] == "origin/main"
    assert any("stale_base" in w for w in d["warnings"])


@requires_git
def test_b2_stale_base_blocks_when_required(
    workspace_root, enable_git_workflow, monkeypatch
):
    monkeypatch.setattr(config, "INTEGRATION_REQUIRE_CURRENT_BASE", True)
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    _advance_origin_main(Path(ws["root_path"]), "remote_only.txt")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1], "base_branch": "main"},
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["error"] == "STALE_BASE"


@requires_git
def test_b2_reconcile_base_merges_upstream(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    _advance_origin_main(Path(ws["root_path"]), "remote_only.txt")

    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={
            "source_branch_ids": [b1],
            "base_branch": "main",
            "reconcile_base": True,
        },
    )
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["status"] == "integrated"
    assert d["base_is_current"] is True
    assert any("reconciled current base" in n for n in d["notes"])
    # The upstream's file is now on the integration branch.
    root = Path(ws["root_path"])
    assert _git(root, "switch", d["integration_branch"]["name"]).returncode == 0
    assert (root / "remote_only.txt").exists()
    assert (root / "a.txt").exists()


@requires_git
def test_b2_current_base_no_warning_regression(
    workspace_root, enable_git_workflow
):
    # No origin/* ref -> staleness undeterminable -> treated current,
    # no behaviour change vs pre-hardening.
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root)
    b1 = _branch_with_commit(ws, "forgeloop/dev-task/dt1", "a.txt", "alpha\n")
    res = client.post(
        f"/workspaces/{ws['id']}/integration-runs",
        json={"source_branch_ids": [b1], "base_branch": "main"},
    )
    assert res.status_code == 201, res.text
    d = res.json()
    assert d["base_is_current"] is True
    assert d["base_upstream"] is None
    assert not any("stale_base" in w for w in d["warnings"])
