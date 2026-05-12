from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import config
from app.llm import get_provider_by_name
from app.llm.base import ProviderError
from app.llm.openai_compatible import OpenAICompatibleProvider, _normalize_usage


def _fake_choice(content: str = "answer"):
    return SimpleNamespace(message=SimpleNamespace(content=content))


def _fake_completion(content: str = "answer", usage: dict | None = None):
    usage_obj = SimpleNamespace(**(usage or {})) if usage else None
    return SimpleNamespace(choices=[_fake_choice(content)], usage=usage_obj)


def test_disabled_by_default():
    assert config.OPENAI_COMPATIBLE_ENABLED is False


def test_construct_requires_base_url_and_key_and_model():
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider(
            provider_name="x", base_url="", api_key="k", model="m"
        )
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider(
            provider_name="x", base_url="https://x", api_key="", model="m"
        )
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider(
            provider_name="x", base_url="https://x", api_key="k", model=""
        )


def test_generate_text_normalizes_content_and_usage():
    with patch("app.llm.openai_compatible.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = _fake_completion(
            content="hello",
            usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
        )
        provider = OpenAICompatibleProvider(
            provider_name="deepseek",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
            model="deepseek-chat",
        )
        result = provider.generate_text("hi")
        assert result == "hello"
        call_kwargs = instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "deepseek-chat"
        assert call_kwargs["messages"][0]["content"] == "hi"
        assert call_kwargs["stream"] is False
        assert provider.last_usage == {
            "prompt_tokens": 5,
            "completion_tokens": 7,
            "total_tokens": 12,
        }


def test_generate_text_empty_content_raises():
    with patch("app.llm.openai_compatible.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.return_value = _fake_completion(content="")
        provider = OpenAICompatibleProvider(
            provider_name="x",
            base_url="https://x",
            api_key="k",
            model="m",
        )
        with pytest.raises(ProviderError):
            provider.generate_text("hi")


def test_generate_text_error_sanitizes_exception():
    with patch("app.llm.openai_compatible.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.side_effect = RuntimeError(
            "boom secret-key=abc"
        )
        provider = OpenAICompatibleProvider(
            provider_name="x",
            base_url="https://x",
            api_key="k",
            model="m",
        )
        with pytest.raises(ProviderError) as exc:
            provider.generate_text("hi")
        # Sanitized: only exception type name surfaces, not the message body.
        assert "secret-key" not in str(exc.value)


def test_normalize_usage_handles_missing():
    assert _normalize_usage(SimpleNamespace(usage=None)) == {}


def test_get_provider_by_name_returns_openai_compatible(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_BASE_URL", "https://x.example.com")
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_API_KEY", "sk-test")
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_MODEL", "m1")
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_PROVIDER_NAME", "deepseek_alias")
    with patch("app.llm.openai_compatible.OpenAI"):
        provider = get_provider_by_name("openai_compatible")
    assert provider.provider_name == "deepseek_alias"
    assert provider.model_name == "m1"


def test_providers_endpoint_marks_openai_compatible_unconfigured_without_key(
    monkeypatch, client
):
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_API_KEY", "")
    res = client.get("/llm/providers")
    by_name = {p["name"]: p for p in res.json()["providers"]}
    assert "openai_compatible" in by_name
    assert by_name["openai_compatible"]["configured"] is False


def test_providers_endpoint_marks_openai_compatible_configured_with_key(
    monkeypatch, client
):
    monkeypatch.setattr(config, "OPENAI_COMPATIBLE_API_KEY", "sk-x")
    res = client.get("/llm/providers")
    by_name = {p["name"]: p for p in res.json()["providers"]}
    assert by_name["openai_compatible"]["configured"] is True
