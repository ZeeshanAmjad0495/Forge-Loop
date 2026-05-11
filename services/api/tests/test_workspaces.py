import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}


def _create_project(name: str = "TestProject") -> dict:
    resp = client.post("/projects", json={"name": name, "description": "d"})
    assert resp.status_code == 201
    return resp.json()


def _create_repo(project_id: str) -> dict:
    resp = client.post(f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    return root


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

def test_create_local_created_workspace_without_root_path_uses_configured_root(workspace_root):
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert Path(body["root_path"]).is_relative_to(workspace_root.resolve())
    assert body["status"] == "ready"
    assert Path(body["root_path"]).is_dir()


def test_create_local_created_workspace_creates_directory_when_requested(workspace_root):
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    )
    assert resp.status_code == 201
    assert Path(resp.json()["root_path"]).is_dir()


def test_create_local_created_workspace_does_not_create_directory_when_false(workspace_root):
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "registered"
    assert not Path(body["root_path"]).exists()


def test_register_local_existing_workspace_under_allowed_root_returns_ready(workspace_root):
    project = _create_project()
    target = workspace_root / "existing"
    target.mkdir()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(target),
            "create_directory": False,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["workspace_type"] == "local_existing"


def test_register_local_existing_workspace_missing_path_returns_missing_status(workspace_root):
    project = _create_project()
    target = workspace_root / "nope"
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(target),
            "create_directory": False,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "missing"
    assert body["error_message"]


def test_reject_path_traversal_returns_400(workspace_root):
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": "../../../etc/passwd",
            "create_directory": False,
        },
    )
    assert resp.status_code == 400


def test_reject_outside_workspace_root_when_flag_false(workspace_root, tmp_path):
    project = _create_project()
    outside = tmp_path / "outside"
    outside.mkdir()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(outside),
            "create_directory": False,
        },
    )
    assert resp.status_code == 400


def test_allow_outside_workspace_root_when_flag_true(workspace_root, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", True)
    project = _create_project()
    outside = tmp_path / "outside_ok"
    outside.mkdir()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_existing",
            "root_path": str(outside),
            "create_directory": False,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "ready"


def test_create_workspace_unknown_project_returns_404(workspace_root):
    resp = client.post(
        "/projects/nonexistent/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    )
    assert resp.status_code == 404


def test_create_workspace_unknown_code_repository_returns_404(workspace_root):
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_created",
            "create_directory": False,
            "code_repository_id": "no-such-repo",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# list / get / patch
# ---------------------------------------------------------------------------

def test_list_workspaces_by_project_filters_correctly(workspace_root):
    proj_a = _create_project("A")
    proj_b = _create_project("B")
    client.post(
        f"/projects/{proj_a['id']}/workspaces",
        json={"name": "wa", "workspace_type": "local_created", "create_directory": False},
    )
    client.post(
        f"/projects/{proj_b['id']}/workspaces",
        json={"name": "wb", "workspace_type": "local_created", "create_directory": False},
    )
    resp = client.get(f"/projects/{proj_a['id']}/workspaces")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "wa"


def test_get_workspace_returns_workspace_and_404_for_missing(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    ).json()
    resp = client.get(f"/workspaces/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]

    assert client.get("/workspaces/missing").status_code == 404


def test_patch_workspace_updates_safe_fields_only(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    ).json()
    resp = client.patch(
        f"/workspaces/{created['id']}",
        json={
            "name": "renamed",
            "description": "new desc",
            # Attempt to mutate forbidden fields — these are not on WorkspaceUpdate,
            # so Pydantic drops them.
            "root_path": "/etc",
            "workspace_type": "manual",
            "project_id": "other",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "renamed"
    assert updated["description"] == "new desc"
    assert updated["root_path"] == created["root_path"]
    assert updated["workspace_type"] == created["workspace_type"]
    assert updated["project_id"] == created["project_id"]


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

def test_inspect_existing_directory_returns_exists_and_is_directory_true(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    ).json()
    resp = client.post(f"/workspaces/{created['id']}/inspect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["exists"] is True
    assert body["is_directory"] is True
    assert body["is_git_repo"] is False

    # last_inspected_at is set
    fetched = client.get(f"/workspaces/{created['id']}").json()
    assert fetched["last_inspected_at"] is not None
    assert fetched["status"] == "ready"


def test_inspect_missing_directory_returns_exists_false_and_updates_status(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": False},
    ).json()
    resp = client.post(f"/workspaces/{created['id']}/inspect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["exists"] is False
    fetched = client.get(f"/workspaces/{created['id']}").json()
    assert fetched["status"] == "missing"


def test_inspect_reports_git_repo_when_dotgit_present_without_running_git(
    workspace_root, monkeypatch
):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not be called from workspace inspect")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)

    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    ).json()
    git_dir = Path(created["root_path"]) / ".git"
    git_dir.mkdir()
    resp = client.post(f"/workspaces/{created['id']}/inspect")
    assert resp.status_code == 200
    assert resp.json()["is_git_repo"] is True
    assert resp.json()["current_branch"] is None  # no git execution
    assert resp.json()["dirty"] is False


def test_inspect_blocked_paths_reports_hits_without_reading_contents(workspace_root, monkeypatch):
    project = _create_project()
    repo = _create_repo(project["id"])
    client.post(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": [".env", "secrets/"],
            "required_checks": [],
            "requires_approval_for": [],
            "protected_branches": ["main"],
            "notes": "",
        },
    )
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_created",
            "create_directory": True,
            "code_repository_id": repo["id"],
        },
    ).json()
    root = Path(created["root_path"])
    env_file = root / ".env"
    env_file.write_text("SECRET=do-not-read\n")
    (root / "secrets").mkdir()

    # Boom if anything tries to read the file contents.
    real_read_text = Path.read_text

    def _read_text_boom(self, *args, **kwargs):
        if self.resolve() == env_file.resolve():
            raise AssertionError("blocked file contents must not be read")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _read_text_boom)

    resp = client.post(f"/workspaces/{created['id']}/inspect")
    assert resp.status_code == 200
    hits = resp.json()["blocked_path_hits"]
    assert ".env" in hits
    assert "secrets/" in hits


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

def test_archive_workspace_marks_archived_and_does_not_delete_directory(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    ).json()
    root = Path(created["root_path"])
    assert root.is_dir()
    resp = client.post(f"/workspaces/{created['id']}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
    # Directory is untouched.
    assert root.is_dir()


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def test_audit_events_written_for_create_inspect_archive(workspace_root):
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    ).json()
    client.post(f"/workspaces/{created['id']}/inspect")
    client.post(f"/workspaces/{created['id']}/archive")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events if e["target_id"] == created["id"]]
    assert "workspace_created" in actions
    assert "workspace_inspected" in actions
    assert "workspace_archived" in actions


# ---------------------------------------------------------------------------
# safety: no shell / http
# ---------------------------------------------------------------------------

def test_no_subprocess_calls_during_workspace_operations(workspace_root, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not be called from workspace operations")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)

    project = _create_project()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={
            "name": "ws",
            "workspace_type": "local_created",
            "create_directory": True,
            "code_repository_id": repo["id"],
        },
    ).json()
    assert client.post(f"/workspaces/{created['id']}/inspect").status_code == 200
    assert client.patch(f"/workspaces/{created['id']}", json={"name": "renamed"}).status_code == 200
    assert client.post(f"/workspaces/{created['id']}/archive").status_code == 200


def test_no_outbound_network_during_workspace_operations(workspace_root, monkeypatch):
    """TestClient dispatches in-process via ASGI, so any real network connection
    would have to use the OS socket primitive. Workspace operations must not."""
    import socket

    def _boom(*args, **kwargs):
        raise AssertionError("outbound network must not be opened by workspace operations")

    monkeypatch.setattr(socket, "create_connection", _boom)

    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created", "create_directory": True},
    ).json()
    assert client.post(f"/workspaces/{created['id']}/inspect").status_code == 200
    assert client.post(f"/workspaces/{created['id']}/archive").status_code == 200
