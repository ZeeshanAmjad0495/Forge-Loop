"""Tests for Release 8 Task 41 — local-first runtime profile endpoint."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import runtime_profile


@pytest.fixture
def runtime_client():
    return TestClient(app)


def test_default_runtime_profile_is_local():
    assert config.FORGELOOP_RUNTIME_PROFILE == "local"


def test_get_runtime_profile_returns_expected_shape(runtime_client):
    res = runtime_client.get("/runtime/profile")
    assert res.status_code == 200
    body = res.json()
    expected_keys = {
        "profile",
        "repository_provider",
        "artifact_provider",
        "workspace_root",
        "command_runner_enabled",
        "git_workflow_enabled",
        "git_commit_enabled",
        "openhands_execution_enabled",
        "github_integration_enabled",
        "firestore_required",
        "mongodb_required",
        "secret_provider",
        "github_token_configured",
        "warnings",
        "errors",
    }
    assert expected_keys.issubset(body.keys())


def test_local_profile_memory_repo_warns(runtime_client, monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    res = runtime_client.get("/runtime/profile")
    assert res.status_code == 200
    body = res.json()
    assert body["profile"] == "local"
    assert body["mongodb_required"] is False
    assert any("memory" in w.lower() and "durable" in w.lower() for w in body["warnings"])


def test_local_profile_local_document_marks_mongodb_required(runtime_client, monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    res = runtime_client.get("/runtime/profile")
    assert res.status_code == 200
    body = res.json()
    assert body["mongodb_required"] is True
    assert body["firestore_required"] is False


def test_hybrid_profile_accepted(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "hybrid")
    s = runtime_profile.build_runtime_summary()
    assert s["profile"] == "hybrid"
    assert not s["errors"]


def test_cloud_profile_accepted(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "firestore")
    s = runtime_profile.build_runtime_summary()
    assert s["profile"] == "cloud"
    assert s["firestore_required"] is True
    assert not s["errors"]


def test_unknown_profile_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "weird")
    s = runtime_profile.build_runtime_summary()
    assert s["profile"] == "weird"
    assert any("Unknown" in e for e in s["errors"])


def test_github_enabled_local_creates_warning(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    s = runtime_profile.build_runtime_summary()
    assert any("github" in w.lower() for w in s["warnings"])


def test_openhands_enabled_creates_warning(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", True)
    s = runtime_profile.build_runtime_summary()
    assert any("openhands" in w.lower() for w in s["warnings"])


def test_cloud_profile_command_runner_warns(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", True)
    s = runtime_profile.build_runtime_summary()
    assert any("command runner" in w.lower() for w in s["warnings"])


def test_no_secrets_in_runtime_summary(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "very-secret-value")
    monkeypatch.setattr(config, "GITHUB_TOKEN", "ghp_secret_token_value_xyz")
    monkeypatch.setattr(config, "KIMI_API_KEY", "kimi-secret-key")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "deepseek-secret-key")
    s = runtime_profile.build_runtime_summary()
    flat = repr(s)
    for forbidden in [
        "very-secret-value",
        "ghp_secret_token_value_xyz",
        "kimi-secret-key",
        "deepseek-secret-key",
    ]:
        assert forbidden not in flat, f"Secret {forbidden} leaked into runtime summary"
    assert s["github_token_configured"] is True


def test_runtime_profile_endpoint_auth_protected(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "test-secret-32-bytes-minimum-length-x")
    client = TestClient(app)
    res = client.get("/runtime/profile")
    assert res.status_code == 401


def test_startup_log_line_is_sanitized(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "GITHUB_TOKEN", "ghp_supersecret_value")
    line = runtime_profile.startup_log_line()
    assert "ghp_supersecret_value" not in line
    assert "profile=local" in line
