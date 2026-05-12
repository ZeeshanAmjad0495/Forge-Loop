"""Tests for Release 8 Task 45 — resolved runtime configuration view."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import runtime_config


@pytest.fixture
def runtime_client():
    return TestClient(app)


def test_resolved_runtime_config_returns_expected_shape(runtime_client):
    res = runtime_client.get("/runtime/config")
    assert res.status_code == 200
    body = res.json()
    for key in ("profile", "repository", "artifacts", "secrets", "execution", "integrations", "warnings", "errors"):
        assert key in body
    assert "provider" in body["repository"]
    assert "provider" in body["artifacts"]
    assert "provider" in body["secrets"]


def test_recommended_local_config_has_no_errors(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "filesystem")
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", False)
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", False)
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", False)
    cfg = runtime_config.build_resolved_runtime_config()
    assert cfg["errors"] == []
    assert cfg["repository"]["provider"] == "local_document"
    assert cfg["artifacts"]["provider"] == "filesystem"
    assert cfg["integrations"]["mongodb_enabled"] is True


def test_memory_config_has_durability_warning(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    cfg = runtime_config.build_resolved_runtime_config()
    assert any("memory" in w.lower() and "durable" in w.lower() for w in cfg["warnings"])
    assert cfg["repository"]["durable"] is False


def test_local_database_artifacts_warning(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")
    cfg = runtime_config.build_resolved_runtime_config()
    assert any("database artifacts" in w.lower() or "bloat" in w.lower() for w in cfg["warnings"])


def test_cloud_profile_with_command_runner_warns(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", True)
    cfg = runtime_config.build_resolved_runtime_config()
    assert any("command runner" in w.lower() for w in cfg["warnings"])


def test_cloud_profile_with_filesystem_artifacts_warns(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "filesystem")
    cfg = runtime_config.build_resolved_runtime_config()
    assert any("filesystem" in w.lower() for w in cfg["warnings"])


def test_secret_values_not_exposed(monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "super-secret-token-value")
    monkeypatch.setattr(config, "GITHUB_TOKEN", "ghp_xyz_secret")
    cfg = runtime_config.build_resolved_runtime_config()
    flat = repr(cfg)
    assert "super-secret-token-value" not in flat
    assert "ghp_xyz_secret" not in flat
    assert cfg["secrets"]["github_token_configured"] is True
    assert cfg["secrets"]["auth_token_secret_configured"] is True


def test_unknown_profile_produces_error(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "weird")
    cfg = runtime_config.build_resolved_runtime_config()
    assert any("Unknown" in e for e in cfg["errors"])


def test_runtime_config_endpoint_auth_protected(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "test-secret-32-bytes-minimum-length-x")
    client = TestClient(app)
    res = client.get("/runtime/config")
    assert res.status_code == 401
