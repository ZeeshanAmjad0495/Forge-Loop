from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_get_providers_default_is_mock_and_mock_configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(config, "KIMI_API_KEY", "")
    response = client.get("/llm/providers")
    assert response.status_code == 200
    data = response.json()
    assert data["default_provider"] == "mock"
    by_name = {p["name"]: p for p in data["providers"]}
    assert by_name["mock"]["configured"] is True
    assert by_name["mock"]["default_model"] == "mock-planning-model"
    for entry in data["providers"]:
        assert set(entry.keys()) == {"name", "configured", "default_model"}


def test_get_providers_marks_deepseek_unconfigured_when_no_key(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    response = client.get("/llm/providers")
    by_name = {p["name"]: p for p in response.json()["providers"]}
    assert by_name["deepseek"]["configured"] is False
    assert by_name["deepseek"]["default_model"] == "deepseek-v4-flash"


def test_get_providers_marks_kimi_unconfigured_when_no_key(monkeypatch):
    monkeypatch.setattr(config, "KIMI_API_KEY", "")
    response = client.get("/llm/providers")
    by_name = {p["name"]: p for p in response.json()["providers"]}
    assert by_name["kimi"]["configured"] is False
    assert by_name["kimi"]["default_model"] == "kimi-k2.6"


def test_get_providers_marks_deepseek_configured_when_key_present(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-test")
    response = client.get("/llm/providers")
    by_name = {p["name"]: p for p in response.json()["providers"]}
    assert by_name["deepseek"]["configured"] is True
