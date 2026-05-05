from openai import OpenAI

from .base import ProviderError


class KimiProvider:
    provider_name = "kimi"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ProviderError("KIMI_API_KEY is required when LLM_PROVIDER=kimi")
        self.model_name = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_text(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        except Exception as e:
            raise ProviderError(f"Kimi call failed: {e}") from e
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ProviderError("Kimi returned empty or malformed content")
        return content
