from .. import config
from .base import LLMProvider, ProviderError
from .deepseek import DeepSeekProvider
from .mock import MockLLMProvider


def get_provider() -> LLMProvider:
    if config.LLM_PROVIDER == "mock":
        return MockLLMProvider()
    if config.LLM_PROVIDER == "deepseek":
        model = config.LLM_MODEL or "deepseek-v4-flash"
        return DeepSeekProvider(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=model,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER!r}. Supported: mock, deepseek")
