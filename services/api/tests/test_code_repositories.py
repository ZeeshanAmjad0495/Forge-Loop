from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}


def _create_project(name: str = "TestProject") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str, payload: dict | None = None) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories",
        json=payload or REPO_PAYLOAD,
    ).json()


# ---------------------------------------------------------------------------
# POST /projects/{id}/code-repositories
# ---------------------------------------------------------------------------

def test_create_code_repository_returns_201_and_shape():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/code-repositories",
        json=REPO_PAYLOAD,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["provider"] == "github"
    assert data["repo_url"] == "https://github.com/org/repo"
    assert data["name"] == "repo"
    assert data["default_branch"] == "main"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_code_repository_unknown_project_returns_404():
    resp = client.post(
        "/projects/nonexistent/code-repositories",
        json=REPO_PAYLOAD,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/code-repositories
# ---------------------------------------------------------------------------

def test_list_project_code_repositories_returns_only_that_projects_repos():
    proj_a = _create_project("ProjA")
    proj_b = _create_project("ProjB")
    _create_repo(proj_a["id"], {**REPO_PAYLOAD, "name": "repo-a1"})
    _create_repo(proj_a["id"], {**REPO_PAYLOAD, "name": "repo-a2"})
    _create_repo(proj_b["id"], {**REPO_PAYLOAD, "name": "repo-b1"})

    resp_a = client.get(f"/projects/{proj_a['id']}/code-repositories")
    resp_b = client.get(f"/projects/{proj_b['id']}/code-repositories")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    names_a = sorted(r["name"] for r in resp_a.json())
    names_b = [r["name"] for r in resp_b.json()]
    assert names_a == ["repo-a1", "repo-a2"]
    assert names_b == ["repo-b1"]


def test_list_project_code_repositories_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/code-repositories")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /code-repositories/{id}
# ---------------------------------------------------------------------------

def test_get_code_repository_returns_repo():
    project = _create_project()
    created = _create_repo(project["id"])
    resp = client.get(f"/code-repositories/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_code_repository_unknown_returns_404():
    resp = client.get("/code-repositories/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /code-repositories/{id}
# ---------------------------------------------------------------------------

def test_patch_code_repository_updates_fields_and_timestamp():
    project = _create_project()
    created = _create_repo(project["id"])
    original_updated_at = created["updated_at"]

    resp = client.patch(
        f"/code-repositories/{created['id']}",
        json={"name": "new-name", "default_branch": "develop", "status": "disabled"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "new-name"
    assert data["default_branch"] == "develop"
    assert data["status"] == "disabled"
    assert data["updated_at"] >= original_updated_at


def test_patch_code_repository_partial_only_changes_provided_fields():
    project = _create_project()
    created = _create_repo(project["id"])

    resp = client.patch(
        f"/code-repositories/{created['id']}",
        json={"name": "patched-name"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "patched-name"
    assert data["provider"] == created["provider"]
    assert data["repo_url"] == created["repo_url"]
    assert data["default_branch"] == created["default_branch"]


def test_patch_code_repository_unknown_returns_404():
    resp = client.patch("/code-repositories/does-not-exist", json={"name": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_create_code_repository_writes_audit_event():
    project = _create_project()
    _create_repo(project["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "code_repository_created" for e in events)


def test_patch_code_repository_writes_audit_event_with_changed_fields():
    project = _create_project()
    created = _create_repo(project["id"])
    client.patch(
        f"/code-repositories/{created['id']}",
        json={"name": "updated"},
    )
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    patch_events = [e for e in events if e["action"] == "code_repository_updated"]
    assert len(patch_events) >= 1
    assert "name" in patch_events[0]["details"]["changed_fields"]
