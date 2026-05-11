import pytest

from app import config


def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    raw = "http://localhost:5173,http://127.0.0.1:5173"
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "*" not in origins


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com")
    origins = [
        o.strip()
        for o in "https://app.example.com,https://admin.example.com".split(",")
        if o.strip()
    ]
    assert origins == ["https://app.example.com", "https://admin.example.com"]


def test_cors_origins_strips_whitespace():
    raw = " http://localhost:5173 , http://127.0.0.1:5173 "
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    assert origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_validate_startup_config_raises_when_auth_enabled_and_secret_empty(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "")
    with pytest.raises(RuntimeError, match="AUTH_TOKEN_SECRET"):
        config.validate_startup_config()


def test_validate_startup_config_ok_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", False)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "")
    config.validate_startup_config()  # must not raise


def test_validate_startup_config_ok_when_auth_enabled_and_secret_set(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "a-sufficiently-long-test-secret-value")
    config.validate_startup_config()  # must not raise


def test_openhands_execution_defaults_are_safe():
    assert config.OPENHANDS_EXECUTION_ENABLED is False
    assert config.OPENHANDS_MODE == "dry_run"
    assert config.OPENHANDS_COMMAND == ""
    assert config.OPENHANDS_TIMEOUT_SECONDS == 1800
    assert config.OPENHANDS_MAX_OUTPUT_BYTES == 200000
    assert config.OPENHANDS_EXECUTION_HARD_CAP_SECONDS == 3600
    assert config.OPENHANDS_ALLOWED_ARGS == []


def test_git_workflow_defaults_are_safe():
    assert config.GIT_WORKFLOW_ENABLED is False
    assert config.GIT_COMMIT_ENABLED is False
    assert config.GIT_ALLOWED_BRANCH_PREFIX == "forgeloop/"
    for protected in ("main", "master", "develop", "production", "release"):
        assert protected in config.GIT_PROTECTED_BRANCHES
    assert config.GIT_TIMEOUT_SECONDS == 60
    assert config.GIT_MAX_DIFF_BYTES == 200000
    assert config.GIT_COMMIT_MESSAGE_MAX_LEN == 2000
    assert config.GIT_BINARY == "git"
