from unittest.mock import MagicMock, patch

import pytest

from app import config
from app.llm import get_provider
from app.llm.base import ProviderError
from app.llm.deepseek import DeepSeekProvider
from app.llm.kimi import KimiProvider
from app.llm.mock import MockLLMProvider


def test_default_provider_is_mock():
    provider = get_provider()
    assert isinstance(provider, MockLLMProvider)


def test_mock_provider_explicitly(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    provider = get_provider()
    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


def test_deepseek_provider_selected(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with patch("app.llm.deepseek.OpenAI"):
        provider = get_provider()
    assert isinstance(provider, DeepSeekProvider)
    assert provider.provider_name == "deepseek"


def test_deepseek_default_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with patch("app.llm.deepseek.OpenAI"):
        provider = get_provider()
    assert provider.model_name == "deepseek-v4-flash"


def test_deepseek_custom_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", "deepseek-chat")
    with patch("app.llm.deepseek.OpenAI"):
        provider = get_provider()
    assert provider.model_name == "deepseek-chat"


def test_deepseek_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with pytest.raises(ProviderError, match="DEEPSEEK_API_KEY"):
        get_provider()


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "unknown-provider")
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider()


def test_kimi_provider_selected(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "kimi")
    monkeypatch.setattr(config, "KIMI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with patch("app.llm.kimi.OpenAI"):
        provider = get_provider()
    assert isinstance(provider, KimiProvider)
    assert provider.provider_name == "kimi"


def test_kimi_default_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "kimi")
    monkeypatch.setattr(config, "KIMI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with patch("app.llm.kimi.OpenAI"):
        provider = get_provider()
    assert provider.model_name == "kimi-k2.6"


def test_kimi_custom_model(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "kimi")
    monkeypatch.setattr(config, "KIMI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "LLM_MODEL", "kimi-k1")
    with patch("app.llm.kimi.OpenAI"):
        provider = get_provider()
    assert provider.model_name == "kimi-k1"


def test_kimi_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "kimi")
    monkeypatch.setattr(config, "KIMI_API_KEY", "")
    monkeypatch.setattr(config, "LLM_MODEL", None)
    with pytest.raises(ProviderError, match="KIMI_API_KEY"):
        get_provider()


def test_kimi_generate_text_mocked():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "# Implementation Brief\nsome content"
    with patch("app.llm.kimi.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        provider = KimiProvider(api_key="sk-test", base_url="https://api.moonshot.ai/v1", model="kimi-k2.6")
        result = provider.generate_text("some prompt")
    assert "# Implementation Brief" in result


def test_kimi_empty_response_raises():
    mock_response = MagicMock()
    mock_response.choices = []
    with patch("app.llm.kimi.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        provider = KimiProvider(api_key="sk-test", base_url="https://api.moonshot.ai/v1", model="kimi-k2.6")
        with pytest.raises(ProviderError, match="empty or malformed"):
            provider.generate_text("some prompt")


def test_deepseek_generate_text_mocked():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "# Implementation Brief\nsome content"
    with patch("app.llm.deepseek.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        provider = DeepSeekProvider(api_key="sk-test", base_url="http://localhost", model="deepseek-v4-flash")
        result = provider.generate_text("some prompt")
    assert "# Implementation Brief" in result


def test_deepseek_generate_text_empty_response_raises():
    mock_response = MagicMock()
    mock_response.choices = []
    with patch("app.llm.deepseek.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        provider = DeepSeekProvider(api_key="sk-test", base_url="http://localhost", model="deepseek-v4-flash")
        with pytest.raises(ProviderError, match="empty or malformed"):
            provider.generate_text("some prompt")
