from typing import Protocol


class ProviderError(Exception):
    pass


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_text(self, prompt: str) -> str: ...
