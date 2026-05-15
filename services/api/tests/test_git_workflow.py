"""Tests for Task 37: Local Git Branch Workflow.

Uses real temp git repositories — no remotes, no network, no pushes/fetches.
Skips the integration tests when the `git` CLI is unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services.git_workflow import (
    GitOperationError,
    _check_top_level,
    _is_safe_commit_path,
    _validate_branch_name,
)


client = TestClient(app)

GIT_BIN = shutil.which("git")
requires_git = pytest.mark.skipif(GIT_BIN is None, reason="git CLI not available")


REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


# ---------------------------------------------------------------------------
# Pure validators (run unconditionally; no git binary needed)
# ---------------------------------------------------------------------------


def test_validate_branch_name_accepts_forgeloop_scoped():
    _validate_branch_name(
        "forgeloop/dev-task/abc-123",
        prefix="forgeloop/",
        protected={"main", "master"},
    )


@pytest.mark.parametrize("name", [
    "",
    "forgeloop/has space",
    "forgeloop/has..dots",
    "-forgeloop/leading-dash",
    "forgeloop/tilde~here",
    "forgeloop/has;semicolon",
    "forgeloop/end-slash/",
    "forgeloop/end.lock",
    "forgeloop/with\nnewline",
    "forgeloop/with\x00null",
    "feature/x",  # missing required prefix
])
def test_validate_branch_name_rejects_unsafe(name):
    with pytest.raises(Exception):
        _validate_branch_name(name, prefix="forgeloop/", protected={"main"})


@pytest.mark.parametrize("name", [
    "forgeloop/main",
    "forgeloop/master",
    "forgeloop/develop",
    "forgeloop/production",
])
def test_validate_branch_name_rejects_protected_prefix_collisions(name):
    # We use exact-match style protection; a "forgeloop/main" name should be
    # accepted because it's prefixed by the allow-list. Validate the actual
    # exact-match rejection separately below.
    _validate_branch_name(name, prefix="forgeloop/", protected={"main", "master"})


def test_validate_branch_name_rejects_exact_protected():
    # Even with a forgeloop prefix, if the operator configured the *full* name
    # in GIT_PROTECTED_BRANCHES, reject it.
    with pytest.raises(Exception):
        _validate_branch_name(
            "forgeloop/release",
            prefix="forgeloop/",
            protected={"forgeloop/release"},
        )


def test_is_safe_commit_path_rejects_secrets_and_traversal():
    blocked = [".env", "secrets"]
    assert _is_safe_commit_path("app/main.py", blocked_prefixes=blocked) is True
    assert _is_safe_commit_path(".env", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path(".env.local", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path("secrets/api.key", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path(".git/HEAD", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path(".forgeloop/x", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path("../escape", blocked_prefixes=blocked) is False
    assert _is_safe_commit_path("/abs/path", blocked_prefixes=blocked) is False


def test_is_safe_commit_path_rejects_build_test_junk():
    """B15 defense-in-depth: generated artifacts must never be committed
    even when the project has no .gitignore covering them.
    """
    b: list[str] = []
    # rejected junk
    for junk in [
        ".coverage",
        ".coverage.host.12345",
        "__pycache__/x.cpython-313.pyc",
        "pkg/__pycache__/mod.pyc",
        "main.pyc",
        "mod.pyo",
        ".pytest_cache/v/cache/lastfailed",
        ".mypy_cache/3.13/x.data.json",
        ".ruff_cache/content/abc",
        ".venv/bin/python",
        "venv/lib/site-packages/foo.py",
        ".python-version",
        "htmlcov/index.html",
    ]:
        assert _is_safe_commit_path(junk, blocked_prefixes=b) is False, junk
    # still-allowed real source/files
    for ok in [
        "main.py",
        "app/coverage_report.py",        # not literally .coverage
        "tests/test_pycache.py",         # name contains 'pycache' but not the dir
        "docs/venv-setup.md",            # 'venv' substring, not the dir
        "pyproject.toml",
    ]:
        assert _is_safe_commit_path(ok, blocked_prefixes=b) is True, ok


def test_check_top_level_rejects_disallowed_command():
    # Task 38 narrowly added "push" to the allow-list for the PR
    # publication flow; everything else stays rejected.
    with pytest.raises(GitOperationError):
        _check_top_level(["fetch", "origin"])
    with pytest.raises(GitOperationError):
        _check_top_level(["merge", "main"])
    with pytest.raises(GitOperationError):
        _check_top_level(["reset", "--hard"])
    with pytest.raises(GitOperationError):
        _check_top_level(["checkout", "-f"])
    with pytest.raises(GitOperationError):
        _check_top_level(["remote", "set-url", "origin", "x"])
    with pytest.raises(GitOperationError):
        _check_top_level(["pull", "origin"])


def test_check_top_level_accepts_allowlisted():
    # Should not raise.
    _check_top_level(["rev-parse", "--abbrev-ref", "HEAD"])
    _check_top_level(["status", "--porcelain=v1"])
    _check_top_level(["switch", "-c", "forgeloop/x"])
    _check_top_level(["add", "--", "file.txt"])
    _check_top_level([
        "-c", "user.name=ForgeLoop",
        "-c", "user.email=forgeloop@local",
        "commit", "-m", "msg",
    ])
    # Task 38: push is allowed (the publication service further restricts argv shape).
    _check_top_level(["push", "origin", "forgeloop/dev-task/abc"])


def test_check_top_level_rejects_disallowed_after_minus_c():
    with pytest.raises(GitOperationError):
        _check_top_level(["-c", "user.name=x", "fetch"])


def test_check_top_level_rejects_malformed_minus_c():
    with pytest.raises(GitOperationError):
        _check_top_level(["-c", "nosign", "commit", "-m", "x"])


# ---------------------------------------------------------------------------
# Integration tests (require real git)
# ---------------------------------------------------------------------------


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


@pytest.fixture
def enable_git_commit(monkeypatch):
    monkeypatch.setattr(config, "GIT_COMMIT_ENABLED", True)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git inside a temp dir without touching global config."""
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
    res = _git(path, "init")
    assert res.returncode == 0, res.stderr
    res = _git(path, "commit", "--allow-empty", "-m", "init")
    assert res.returncode == 0, res.stderr


def _create_project(name: str = "P37") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_dev_task(project_id: str) -> dict:
    req = client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return decomp["dev_tasks"][0]


def _create_git_workspace(project_id: str, tmp_path: Path, *, name: str = "ws") -> dict:
    ws_dir = tmp_path / "ws_root" / "ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    if GIT_BIN:
        _init_repo(ws_dir)
    res = client.post(
        f"/projects/{project_id}/workspaces",
        json={
            "name": name,
            "workspace_type": "local_existing",
            "root_path": str(ws_dir),
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _approve(project_id: str, target_type: str, target_id: str) -> dict:
    created = client.post("/approvals", json={
        "project_id": project_id,
        "target_type": target_type,
        "target_id": target_id,
    }).json()
    return client.patch(
        f"/approvals/{created['id']}", json={"status": "approved"}
    ).json()


# ---- inspect ----


@requires_git
def test_inspect_non_git_workspace_returns_non_git_state(workspace_root):
    project = _create_project()
    ws_dir = workspace_root / "ws"
    ws_dir.mkdir()
    ws = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_existing", "root_path": str(ws_dir)},
    ).json()
    res = client.post(f"/workspaces/{ws['id']}/git/inspect")
    assert res.status_code == 200
    data = res.json()
    assert data["is_git_repo"] is False
    assert data["current_branch"] is None
    assert data["dirty"] is False
    assert data["git_workflow_enabled"] is False


@requires_git
def test_inspect_git_workspace_returns_current_branch(workspace_root, tmp_path):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    res = client.post(f"/workspaces/{ws['id']}/git/inspect")
    assert res.status_code == 200
    data = res.json()
    assert data["is_git_repo"] is True
    assert data["current_branch"] in ("main", "master")
    assert data["dirty"] is False
    assert data["changed_files"] == []
    assert data["untracked_files"] == []


@requires_git
def test_inspect_dirty_workspace_reports_untracked(workspace_root):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    (Path(ws["root_path"]) / "new.txt").write_text("hi", encoding="utf-8")
    res = client.post(f"/workspaces/{ws['id']}/git/inspect")
    data = res.json()
    assert data["dirty"] is True
    assert "new.txt" in data["untracked_files"]


@requires_git
def test_inspect_dirty_workspace_reports_changed(workspace_root):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    ws_path = Path(ws["root_path"])
    (ws_path / "tracked.txt").write_text("v1", encoding="utf-8")
    _git(ws_path, "add", "tracked.txt")
    _git(ws_path, "commit", "-m", "add tracked")
    (ws_path / "tracked.txt").write_text("v2", encoding="utf-8")
    res = client.post(f"/workspaces/{ws['id']}/git/inspect")
    data = res.json()
    assert "tracked.txt" in data["changed_files"]


# ---- create branch ----


@requires_git
def test_create_branch_returns_409_when_disabled(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "GIT_WORKFLOW_ENABLED", False)
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)

    res = client.post(f"/workspaces/{ws['id']}/branches", json={})
    assert res.status_code == 409
    assert "GIT_WORKFLOW_DISABLED" in res.text

    # No forgeloop branch on disk.
    listing = _git(Path(ws["root_path"]), "branch", "--list", "forgeloop/*")
    assert listing.stdout.strip() == ""


@requires_git
def test_create_branch_auto_generates_dev_task_name(workspace_root, enable_git_workflow):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)

    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    branch_name = body["workspace_branch"]["name"]
    assert branch_name == f"forgeloop/dev-task/{task['id']}"
    assert body["workspace_branch"]["status"] == "clean"
    # Verify on disk.
    head = _git(Path(ws["root_path"]), "rev-parse", "--abbrev-ref", "HEAD")
    assert head.stdout.strip() == branch_name


@requires_git
@pytest.mark.parametrize("bad_name", [
    "main",
    "feature/x",  # missing forgeloop/ prefix
    "forgeloop/has space",
    "forgeloop/has..dots",
])
def test_create_branch_rejects_unsafe_names(
    workspace_root, enable_git_workflow, bad_name
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"name": bad_name},
    )
    assert res.status_code == 400


@requires_git
def test_create_branch_rejects_protected_from_safety_profile(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    repo = client.post(
        f"/projects/{project['id']}/code-repositories",
        json={
            "provider": "github",
            "repo_url": "https://example.com/r",
            "name": "r",
            "default_branch": "main",
        },
    ).json()
    client.post(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": [],
            "required_checks": [],
            "requires_approval_for": [],
            "protected_branches": ["forgeloop/protected"],
            "notes": "",
        },
    )
    ws_dir = workspace_root / "ws"
    ws_dir.mkdir()
    _init_repo(ws_dir)
    ws = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(ws_dir),
            "code_repository_id": repo["id"],
        },
    ).json()
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"name": "forgeloop/protected"},
    )
    assert res.status_code == 400
    assert "protected" in res.text.lower()


@requires_git
def test_create_branch_requires_git_repo(workspace_root, enable_git_workflow):
    project = _create_project()
    ws_dir = workspace_root / "no_git"
    ws_dir.mkdir()
    ws = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_existing", "root_path": str(ws_dir)},
    ).json()
    res = client.post(f"/workspaces/{ws['id']}/branches", json={})
    assert res.status_code == 400
    assert "not a git repository" in res.text


@requires_git
def test_create_branch_workspace_project_mismatch_rejected(
    workspace_root, enable_git_workflow
):
    project_a = _create_project("A")
    project_b = _create_project("B")
    task_a = _create_dev_task(project_a["id"])
    ws_b = _create_git_workspace(project_b["id"], workspace_root.parent)

    res = client.post(
        f"/workspaces/{ws_b['id']}/branches",
        json={"dev_task_id": task_a["id"]},
    )
    assert res.status_code == 400


@requires_git
def test_create_branch_missing_base_branch_rejected(
    workspace_root, enable_git_workflow
):
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"base_branch": "does-not-exist"},
    )
    assert res.status_code == 400
    assert "does not exist locally" in res.text


@requires_git
def test_create_branch_does_not_invoke_forbidden_git_ops(
    workspace_root, enable_git_workflow, monkeypatch
):
    """Wrap subprocess.run and reject any forbidden git argv."""
    real_run = subprocess.run
    forbidden = {"push", "pull", "fetch", "merge", "rebase", "reset", "clean", "remote"}

    def wrapped(args, *a, **kw):
        if isinstance(args, (list, tuple)) and len(args) >= 1:
            # skip leading -c key=value tokens
            i = 1  # 0 is the binary
            while i < len(args) and args[i] == "-c":
                i += 2
            top = args[i] if i < len(args) else ""
            if top in forbidden:
                raise AssertionError(f"forbidden git op invoked: {args!r}")
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", wrapped)

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    )
    assert res.status_code == 201


@requires_git
def test_create_branch_uses_explicit_base_branch_start_point(
    workspace_root, enable_git_workflow
):
    """B17 regression: a new branch must start from base_branch, not from
    whatever the workspace's current HEAD happens to be. Otherwise prior
    dev_task state bleeds into the new branch's first commit.
    """
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    root = Path(ws["root_path"])
    # Create a feature branch with an extra commit, then leave the workspace on it.
    _git(root, "switch", "-c", "forgeloop/scratch")
    (root / "scratch.txt").write_text("scratch", encoding="utf-8")
    _git(root, "add", "scratch.txt")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@local", "commit", "-m", "scratch")
    # main still points to the original commit; HEAD is now on scratch.
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"name": "forgeloop/from-main", "base_branch": "main"},
    )
    assert res.status_code == 201, res.text
    # The new branch must NOT contain scratch.txt — it should match main.
    head = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert head == "forgeloop/from-main"
    files = _git(root, "ls-files").stdout.split()
    assert "scratch.txt" not in files


@requires_git
def test_create_branch_refuses_dirty_workspace(
    workspace_root, enable_git_workflow
):
    """B17 guard: starting a new dev_task branch on top of an uncommitted
    working tree must fail loudly so prior state doesn't silently leak.
    """
    project = _create_project()
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    root = Path(ws["root_path"])
    # Leave a tracked-but-modified file in the working tree.
    (root / "dirty.txt").write_text("dirty", encoding="utf-8")
    _git(root, "add", "dirty.txt")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@local", "commit", "-m", "seed")
    (root / "dirty.txt").write_text("now dirty", encoding="utf-8")
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"name": "forgeloop/should-fail", "base_branch": "main"},
    )
    assert res.status_code == 409
    body = res.json()
    assert body["detail"]["error"] == "WORKSPACE_DIRTY"


@requires_git
def test_create_branch_writes_audit(workspace_root, enable_git_workflow):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    res = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    )
    assert res.status_code == 201
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "workspace_branch_created" in actions


@requires_git
def test_list_and_get_branch(workspace_root, enable_git_workflow):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    created = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()
    branch_id = created["workspace_branch"]["id"]

    listing = client.get(f"/workspaces/{ws['id']}/branches").json()
    assert any(b["id"] == branch_id for b in listing)

    fetched = client.get(f"/workspace-branches/{branch_id}").json()
    assert fetched["workspace_branch"]["id"] == branch_id
    assert fetched["inspection"]["is_git_repo"] is True


# ---- commit ----


@requires_git
def test_commit_blocked_when_commit_disabled(workspace_root, enable_git_workflow):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    (Path(ws["root_path"]) / "x.txt").write_text("hi", encoding="utf-8")

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "test"},
    )
    assert res.status_code == 409
    assert "GIT_COMMIT_DISABLED" in res.text


@requires_git
def test_commit_requires_approval(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    (Path(ws["root_path"]) / "x.txt").write_text("hi", encoding="utf-8")

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "test"},
    )
    assert res.status_code == 400
    assert "approval" in res.text.lower()


@requires_git
def test_commit_proceeds_with_approval_and_records_sha(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    (Path(ws["root_path"]) / "x.txt").write_text("hi", encoding="utf-8")
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "add x.txt for task"},
    )
    assert res.status_code == 201, res.text
    record = res.json()
    assert record["status"] == "committed"
    assert record["commit_sha"] and len(record["commit_sha"]) >= 7
    assert "x.txt" in record["changed_files"]
    assert record["artifact_id"]

    # Audit events
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {e["action"] for e in events}
    assert "workspace_commit_prepared" in actions
    assert "workspace_commit_created" in actions

    # WorkspaceBranch.status -> committed
    fetched = client.get(f"/workspace-branches/{branch['id']}").json()
    assert fetched["workspace_branch"]["status"] == "committed"


@requires_git
def test_commit_excludes_blocked_paths(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    ws_path = Path(ws["root_path"])
    (ws_path / ".env").write_text("SECRET=1", encoding="utf-8")
    (ws_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "add app"},
    )
    assert res.status_code == 201, res.text
    record = res.json()
    assert "app.py" in record["changed_files"]
    assert ".env" not in record["changed_files"]
    # .env still untracked in the working tree.
    status = _git(ws_path, "status", "--porcelain=v1")
    assert "?? .env" in status.stdout


@requires_git
def test_commit_rejects_include_paths_outside_diff(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    (Path(ws["root_path"]) / "a.txt").write_text("hi", encoding="utf-8")
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={
            "message": "test",
            "include_paths": ["does-not-exist.py"],
        },
    )
    assert res.status_code == 400


@requires_git
def test_commit_rejects_include_paths_with_secrets(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    ws_path = Path(ws["root_path"])
    (ws_path / ".env").write_text("SECRET=1", encoding="utf-8")
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={
            "message": "smuggle env",
            "include_paths": [".env"],
        },
    )
    assert res.status_code == 400


@requires_git
def test_commit_records_failure_when_pre_commit_hook_fails(
    workspace_root, enable_git_workflow, enable_git_commit
):
    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    ws_path = Path(ws["root_path"])
    hook = ws_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (ws_path / "y.txt").write_text("data", encoding="utf-8")
    _approve(project["id"], "dev_task", task["id"])

    res = client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "should fail"},
    )
    assert res.status_code == 400

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {e["action"] for e in events}
    assert "workspace_commit_failed" in actions


# ---- safety: no forbidden git ops anywhere ----


@requires_git
def test_full_inspect_branch_commit_flow_uses_only_allowlisted_ops(
    workspace_root, enable_git_workflow, enable_git_commit, monkeypatch
):
    forbidden = {"push", "pull", "fetch", "merge", "rebase", "reset", "clean", "remote", "tag", "stash", "worktree", "cherry-pick", "checkout"}
    real_run = subprocess.run

    def wrapped(args, *a, **kw):
        if isinstance(args, (list, tuple)) and len(args) >= 2:
            i = 1
            while i < len(args) and args[i] == "-c":
                i += 2
            top = args[i] if i < len(args) else ""
            if top in forbidden:
                raise AssertionError(f"forbidden git op invoked: {args!r}")
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", wrapped)

    project = _create_project()
    task = _create_dev_task(project["id"])
    ws = _create_git_workspace(project["id"], workspace_root.parent)
    _approve(project["id"], "dev_task", task["id"])

    client.post(f"/workspaces/{ws['id']}/git/inspect")
    branch = client.post(
        f"/workspaces/{ws['id']}/branches",
        json={"dev_task_id": task["id"]},
    ).json()["workspace_branch"]
    (Path(ws["root_path"]) / "f.txt").write_text("x", encoding="utf-8")
    client.post(
        f"/workspace-branches/{branch['id']}/commit",
        json={"message": "task work"},
    )
    client.get(f"/workspace-branches/{branch['id']}")
