from .. import config
from .base import LLMProvider, ProviderError
from .deepseek import DeepSeekProvider
from .kimi import KimiProvider
from .mock import MockLLMProvider
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider


_PROVIDER_REGISTRY = {
    "mock": {"default_model": "mock-planning-model", "api_key_attr": None},
    "deepseek": {"default_model": "deepseek-v4-flash", "api_key_attr": "DEEPSEEK_API_KEY"},
    "kimi": {"default_model": "kimi-k2.6", "api_key_attr": "KIMI_API_KEY"},
    "ollama": {"default_model": "qwen2.5-coder:3b", "api_key_attr": None},
    "openai_compatible": {
        "default_model": "gpt-4o-mini",
        "api_key_attr": "OPENAI_COMPATIBLE_API_KEY",
    },
}


def get_default_provider_name() -> str:
    return config.LLM_PROVIDER


def _is_configured(name: str) -> bool:
    attr = _PROVIDER_REGISTRY[name]["api_key_attr"]
    return attr is None or bool(getattr(config, attr))


def _resolved_default_model(name: str) -> str:
    return config.LLM_MODEL or _PROVIDER_REGISTRY[name]["default_model"]


def list_provider_status() -> list[dict]:
    return [
        {
            "name": name,
            "configured": _is_configured(name),
            "default_model": _resolved_default_model(name),
        }
        for name in _PROVIDER_REGISTRY
    ]


def get_provider_by_name(name: str) -> LLMProvider:
    if name not in _PROVIDER_REGISTRY:
        supported = ", ".join(_PROVIDER_REGISTRY)
        raise ValueError(f"Unknown provider: {name!r}. Supported: {supported}")
    model = _resolved_default_model(name)
    if name == "mock":
        return MockLLMProvider()
    if name == "deepseek":
        return DeepSeekProvider(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=model,
        )
    if name == "kimi":
        return KimiProvider(
            api_key=config.KIMI_API_KEY,
            base_url=config.KIMI_BASE_URL,
            model=model,
        )
    if name == "ollama":
        return OllamaProvider(
            base_url=config.OLLAMA_BASE_URL,
            model=model,
            timeout_seconds=config.OLLAMA_TIMEOUT_SECONDS,
        )
    if name == "openai_compatible":
        compat_model = config.OPENAI_COMPATIBLE_MODEL or model
        return OpenAICompatibleProvider(
            provider_name=config.OPENAI_COMPATIBLE_PROVIDER_NAME,
            base_url=config.OPENAI_COMPATIBLE_BASE_URL,
            api_key=config.OPENAI_COMPATIBLE_API_KEY,
            model=compat_model,
            timeout_seconds=config.OPENAI_COMPATIBLE_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unknown provider: {name!r}")


def get_provider() -> LLMProvider:
    return get_provider_by_name(get_default_provider_name())
