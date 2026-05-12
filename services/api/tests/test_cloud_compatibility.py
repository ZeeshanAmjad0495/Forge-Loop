"""Tests for Release 8 Task 46 — cloud profile compatibility check."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import cloud_compatibility


@pytest.fixture
def runtime_client():
    return TestClient(app)


def _check(report, name):
    for c in report["checks"]:
        if c["name"] == name:
            return c
    raise AssertionError(f"Check {name!r} not found in report")


def test_endpoint_returns_expected_shape(runtime_client):
    res = runtime_client.get("/runtime/cloud-compatibility")
    assert res.status_code == 200
    body = res.json()
    assert {"compatible", "profile", "checks", "warnings", "errors"}.issubset(body.keys())
    for c in body["checks"]:
        assert {"name", "status", "message"}.issubset(c.keys())
        assert c["status"] in ("pass", "warning", "fail")


def test_local_profile_reports_cloud_optional(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "local")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert report["profile"] == "local"
    assert report["cloud_required"] is False


def test_cloud_profile_with_firestore_passes(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "firestore")
    monkeypatch.setattr(config, "GCP_PROJECT_ID", "my-gcp-project")
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", False)
    monkeypatch.setattr(config, "OPENHANDS_EXECUTION_ENABLED", False)
    monkeypatch.setattr(config, "GIT_WORKFLOW_ENABLED", False)
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", False)
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "x" * 40)
    monkeypatch.setattr(config, "CORS_ALLOWED_ORIGINS", ["https://app.example.com"])
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert report["compatible"] is True
    assert _check(report, "repository_provider")["status"] == "pass"
    assert _check(report, "firestore_config")["status"] == "pass"


def test_cloud_profile_with_memory_provider_fails(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "repository_provider")["status"] == "fail"
    assert report["compatible"] is False


def test_cloud_profile_with_command_runner_warns(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "COMMAND_RUNNER_ENABLED", True)
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "command_runner")["status"] == "warning"


def test_cloud_profile_with_filesystem_artifacts_warns(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "ARTIFACT_STORAGE_PROVIDER", "filesystem")
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "artifact_provider")["status"] == "warning"


def test_github_enabled_without_token_fails(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "cloud")
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_TOKEN", "")
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "github_integration")["status"] == "fail"
    assert report["compatible"] is False


def test_cors_wildcard_warns(monkeypatch):
    monkeypatch.setattr(config, "CORS_ALLOWED_ORIGINS", ["*"])
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "cors_origins")["status"] == "warning"


def test_no_secrets_in_report(monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "super-secret-token")
    monkeypatch.setattr(config, "GITHUB_TOKEN", "ghp_my_secret_token")
    report = cloud_compatibility.build_cloud_compatibility_report()
    flat = repr(report)
    assert "super-secret-token" not in flat
    assert "ghp_my_secret_token" not in flat


def test_unknown_profile_fails(monkeypatch):
    monkeypatch.setattr(config, "FORGELOOP_RUNTIME_PROFILE", "weird")
    report = cloud_compatibility.build_cloud_compatibility_report()
    assert _check(report, "runtime_profile")["status"] == "fail"


def test_endpoint_auth_protected(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "test-secret-32-bytes-minimum-length-x")
    client = TestClient(app)
    res = client.get("/runtime/cloud-compatibility")
    assert res.status_code == 401
