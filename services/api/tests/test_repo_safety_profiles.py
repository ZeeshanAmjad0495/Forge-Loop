from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}

PROFILE_PAYLOAD = {
    "work_safe_mode": True,
    "allowed_actions": ["read_code"],
    "blocked_paths": [".env"],
    "required_checks": ["tests"],
    "requires_approval_for": ["create_pr"],
    "protected_branches": ["main"],
    "notes": "test profile",
}


def _create_project() -> dict:
    return client.post("/projects", json={"name": "SafetyP", "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories",
        json=REPO_PAYLOAD,
    ).json()


# ---------------------------------------------------------------------------
# GET /code-repositories/{id}/safety-profile — default when unset
# ---------------------------------------------------------------------------

def test_get_safety_profile_returns_default_when_unset():
    project = _create_project()
    repo = _create_repo(project["id"])
    resp = client.get(f"/code-repositories/{repo['id']}/safety-profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["work_safe_mode"] is True
    assert ".env" in data["blocked_paths"]
    assert "create_pr" in data["requires_approval_for"]
    assert data["protected_branches"] == ["main", "master"]
    assert "read_code" in data["allowed_actions"]


def test_get_safety_profile_unknown_repo_returns_404():
    resp = client.get("/code-repositories/does-not-exist/safety-profile")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /code-repositories/{id}/safety-profile — create / replace
# ---------------------------------------------------------------------------

def test_post_safety_profile_creates_and_returns():
    project = _create_project()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/code-repositories/{repo['id']}/safety-profile",
        json=PROFILE_PAYLOAD,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code_repository_id"] == repo["id"]
    assert data["work_safe_mode"] is True
    assert data["notes"] == "test profile"

    # GET should return same data
    get_resp = client.get(f"/code-repositories/{repo['id']}/safety-profile")
    assert get_resp.status_code == 200
    assert get_resp.json()["notes"] == "test profile"


def test_post_safety_profile_replaces_previous_profile():
    project = _create_project()
    repo = _create_repo(project["id"])
    client.post(f"/code-repositories/{repo['id']}/safety-profile", json=PROFILE_PAYLOAD)
    resp2 = client.post(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={**PROFILE_PAYLOAD, "notes": "replaced"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["notes"] == "replaced"
    # Only one profile should exist
    get_resp = client.get(f"/code-repositories/{repo['id']}/safety-profile")
    assert get_resp.json()["notes"] == "replaced"


def test_post_safety_profile_unknown_repo_returns_404():
    resp = client.post(
        "/code-repositories/does-not-exist/safety-profile",
        json=PROFILE_PAYLOAD,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /code-repositories/{id}/safety-profile
# ---------------------------------------------------------------------------

def test_patch_safety_profile_updates_fields():
    project = _create_project()
    repo = _create_repo(project["id"])
    client.post(f"/code-repositories/{repo['id']}/safety-profile", json=PROFILE_PAYLOAD)

    resp = client.patch(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={"notes": "patched", "work_safe_mode": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "patched"
    assert data["work_safe_mode"] is False
    # Untouched fields preserved
    assert data["allowed_actions"] == ["read_code"]
    assert data["blocked_paths"] == [".env"]


def test_patch_safety_profile_when_unset_creates_from_default():
    project = _create_project()
    repo = _create_repo(project["id"])

    resp = client.patch(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={"work_safe_mode": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["work_safe_mode"] is False
    # Other fields should match defaults
    assert ".env" in data["blocked_paths"]
    assert "read_code" in data["allowed_actions"]
    assert data["protected_branches"] == ["main", "master"]


def test_patch_safety_profile_unknown_repo_returns_404():
    resp = client.patch(
        "/code-repositories/does-not-exist/safety-profile",
        json={"notes": "x"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_safety_profile_post_writes_audit_event():
    project = _create_project()
    repo = _create_repo(project["id"])
    client.post(f"/code-repositories/{repo['id']}/safety-profile", json=PROFILE_PAYLOAD)
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "repo_safety_profile_updated" for e in events)


def test_safety_profile_patch_writes_audit_event():
    project = _create_project()
    repo = _create_repo(project["id"])
    client.patch(
        f"/code-repositories/{repo['id']}/safety-profile",
        json={"notes": "from patch"},
    )
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "repo_safety_profile_updated" for e in events)
