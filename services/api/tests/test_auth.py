from datetime import datetime, timezone, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)

_TEST_EMAIL = "admin@example.com"
_TEST_PASSWORD = "s3cret"
_TEST_SECRET = "test-secret-32-bytes-minimum-length-x"


def _enable_auth(monkeypatch):
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


def test_login_succeeds_with_valid_credentials(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.post("/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_fails_with_invalid_password(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.post("/auth/login", json={"email": _TEST_EMAIL, "password": "wrongpassword"})
    assert res.status_code == 401
    # generic message — must not reveal which field was wrong
    detail = res.json()["detail"].lower()
    assert detail == "invalid email or password"


def test_login_fails_with_unknown_email(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.post("/auth/login", json={"email": "other@example.com", "password": _TEST_PASSWORD})
    assert res.status_code == 401


def test_login_email_case_insensitive(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.post("/auth/login", json={"email": "Admin@Example.COM", "password": _TEST_PASSWORD})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_me_returns_email_with_valid_token(monkeypatch):
    token = _get_token(monkeypatch)
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == _TEST_EMAIL


def test_me_rejects_request_without_token(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_rejects_invalid_token(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert res.status_code == 401


def test_me_rejects_expired_token(monkeypatch):
    _enable_auth(monkeypatch)
    expired_payload = {
        "sub": _TEST_EMAIL,
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, _TEST_SECRET, algorithm="HS256")
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_protected_endpoint_requires_token(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.post("/tickets", json={"title": "Test", "description": "Test desc"})
    assert res.status_code == 401


def test_protected_endpoint_accepts_valid_token(monkeypatch):
    token = _get_token(monkeypatch)
    res = client.post(
        "/tickets",
        json={"title": "Auth ticket", "description": "Created with token"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["title"] == "Auth ticket"


def test_login_returns_500_when_secret_missing(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_ADMIN_EMAIL", _TEST_EMAIL)
    monkeypatch.setattr(config, "AUTH_ADMIN_PASSWORD", _TEST_PASSWORD)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "")
    res = client.post("/auth/login", json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD})
    assert res.status_code == 500
    assert "misconfigured" in res.json()["detail"].lower()
    assert _TEST_SECRET not in res.text  # no secret leakage


def test_health_remains_public_when_auth_enabled(monkeypatch):
    _enable_auth(monkeypatch)
    res = client.get("/health")
    assert res.status_code == 200
