import json
from io import BytesIO
from unittest.mock import patch

import pytest

from app import config
from app.llm import get_provider_by_name
from app.llm.base import ProviderError
from app.llm.ollama import OllamaProvider
from app.services.model_routing import ModelRoutePreviewRequest, decide_route


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ollama_disabled_by_default():
    # OLLAMA_ENABLED defaults to False
    assert config.OLLAMA_ENABLED is False


def test_generate_text_builds_chat_request_and_parses_response():
    provider = OllamaProvider(base_url="http://localhost:11434", model="m")
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse({"message": {"content": "hi"}})

    with patch("app.llm.ollama.urllib_request.urlopen", side_effect=_fake_urlopen):
        result = provider.generate_text("ping")

    assert result == "hi"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["model"] == "m"
    assert captured["body"]["messages"][0]["content"] == "ping"
    assert captured["body"]["stream"] is False


def test_generate_text_accepts_response_field():
    provider = OllamaProvider(base_url="http://localhost:11434", model="m")

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse({"response": "fallback content"})

    with patch("app.llm.ollama.urllib_request.urlopen", side_effect=_fake_urlopen):
        assert provider.generate_text("p") == "fallback content"


def test_generate_text_raises_on_empty_content():
    provider = OllamaProvider(base_url="http://localhost:11434", model="m")

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse({"message": {"content": ""}})

    with patch("app.llm.ollama.urllib_request.urlopen", side_effect=_fake_urlopen):
        with pytest.raises(ProviderError):
            provider.generate_text("p")


def test_generate_text_handles_connection_error():
    from urllib.error import URLError

    provider = OllamaProvider(base_url="http://localhost:11434", model="m")

    def _fake_urlopen(req, timeout=None):
        raise URLError("connection refused")

    with patch("app.llm.ollama.urllib_request.urlopen", side_effect=_fake_urlopen):
        with pytest.raises(ProviderError) as exc:
            provider.generate_text("p")
        assert "Ollama call failed" in str(exc.value)


def test_is_available_returns_false_when_unreachable():
    provider = OllamaProvider(base_url="http://localhost:11434", model="m")
    with patch(
        "app.llm.ollama.urllib_request.urlopen", side_effect=ConnectionRefusedError
    ):
        assert provider.is_available() is False


def test_get_provider_by_name_returns_ollama(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(config, "OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:3b")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    provider = get_provider_by_name("ollama")
    assert provider.provider_name == "ollama"
    assert provider.model_name == "qwen2.5-coder:3b"


def test_routing_selects_ollama_for_artifact_summary_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="artifact_summary")
    )
    assert decision.selected_provider == "ollama"


def test_routing_does_not_select_ollama_for_coding(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="coding")
    )
    assert decision.selected_provider != "ollama"


def test_providers_endpoint_includes_ollama(client):
    res = client.get("/llm/providers")
    assert res.status_code == 200
    by_name = {p["name"]: p for p in res.json()["providers"]}
    assert "ollama" in by_name
    assert by_name["ollama"]["configured"] is True
    assert by_name["ollama"]["default_model"]
