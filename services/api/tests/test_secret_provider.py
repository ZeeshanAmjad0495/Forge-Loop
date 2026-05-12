"""Tests for Release 8 Task 44 — env/local secret provider."""

import pytest

from app import config
from app.services import secrets as secret_service


def test_env_provider_returns_env_value(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.setenv("TEST_SECRET_ABC", "hello")
    assert secret_service.get_secret("TEST_SECRET_ABC") == "hello"


def test_missing_optional_secret_returns_none(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.delenv("TEST_SECRET_DEF", raising=False)
    assert secret_service.get_secret("TEST_SECRET_DEF") is None


def test_empty_env_value_treated_as_missing(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.setenv("TEST_SECRET_EMPTY", "")
    assert secret_service.get_secret("TEST_SECRET_EMPTY") is None


def test_require_secret_raises_when_missing(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.delenv("TEST_SECRET_GHI", raising=False)
    with pytest.raises(secret_service.SecretMissingError) as excinfo:
        secret_service.require_secret("TEST_SECRET_GHI", purpose="testing")
    msg = str(excinfo.value)
    assert "TEST_SECRET_GHI" in msg
    assert "testing" in msg


def test_require_secret_error_does_not_include_value(monkeypatch):
    """The error must reference the name only — never the value."""
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.delenv("TEST_SECRET_JKL", raising=False)
    try:
        secret_service.require_secret("TEST_SECRET_JKL", purpose="purpose-x")
    except secret_service.SecretMissingError as exc:
        # Reasonable: the message should not include common secret-looking
        # substrings beyond the env var name.
        assert "ghp_" not in str(exc)
        assert "sk-" not in str(exc)


def test_redact_secret_value():
    assert secret_service.redact_secret_value("supersecret") == "***redacted***"
    assert secret_service.redact_secret_value(None) == ""
    assert secret_service.redact_secret_value("") == ""


def test_unsupported_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "vault")
    with pytest.raises(secret_service.SecretMissingError):
        secret_service.get_secret("ANYTHING")


def test_provider_name(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    assert secret_service.provider_name() == "env"


def test_github_token_lookup_via_provider(monkeypatch):
    monkeypatch.setattr(config, "SECRET_PROVIDER", "env")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_some_token")
    assert secret_service.get_secret("GITHUB_TOKEN") == "ghp_some_token"
