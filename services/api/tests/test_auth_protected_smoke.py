"""Auth-enabled smoke tests.

Verifies that auth protection applies across representative route groups beyond
the auth endpoints themselves. Auth is enabled per-test via monkeypatch; the
conftest `disable_auth_by_default` autouse fixture still applies globally, so
these tests must explicitly opt in.
"""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)

_TEST_EMAIL = "admin@example.com"
_TEST_PASSWORD = "s3cret"
_TEST_SECRET = "test-secret-32-bytes-minimum-length-x"


def _enable_auth(monkeypatch) -> None:
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_ADMIN_EMAIL", _TEST_EMAIL)
    monkeypatch.setattr(config, "AUTH_ADMIN_PASSWORD", _TEST_PASSWORD)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", _TEST_SECRET)
    monkeypatch.setattr(config, "AUTH_TOKEN_TTL_SECONDS", 3600)


def _get_token(monkeypatch) -> str:
    _enable_auth(monkeypatch)
    res = client.post("/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert res.status_code == 200
    return res.json()["access_token"]


# ---------------------------------------------------------------------------
# Representative protected endpoints
# ---------------------------------------------------------------------------

_PROTECTED_GET_ENDPOINTS = [
    "/projects",
    "/projects/any-id/requirements",
    "/projects/any-id/check-definitions",
    "/projects/any-id/pr-drafts",
    "/projects/any-id/incidents",
]


@pytest.mark.parametrize("path", _PROTECTED_GET_ENDPOINTS)
def test_protected_endpoint_requires_token(monkeypatch, path):
    """Unauthenticated requests to protected endpoints return 401, not 404 or 200."""
    _enable_auth(monkeypatch)
    res = client.get(path)
    assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"


@pytest.mark.parametrize("path", _PROTECTED_GET_ENDPOINTS)
def test_protected_endpoint_accepts_valid_token(monkeypatch, path):
    """Authenticated requests with a valid token are processed (not rejected at auth layer)."""
    token = _get_token(monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}

    # For project-scoped endpoints that embed a project id, first create a project.
    if "/any-id/" in path:
        proj_res = client.post(
            "/projects",
            json={"name": "Smoke", "description": "auth smoke"},
            headers=headers,
        )
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]
        real_path = path.replace("any-id", project_id)
    else:
        real_path = path

    res = client.get(real_path, headers=headers)
    # 200 (list) or 404 (missing child resource) are both auth-accepted responses.
    assert res.status_code in (200, 404), (
        f"Expected 200 or 404 for {real_path}, got {res.status_code}: {res.text}"
    )
