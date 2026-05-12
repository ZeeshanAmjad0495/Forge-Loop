"""Generic OpenAI-compatible LLM provider (Release 9, Task 55).

Adapter for any service exposing OpenAI's ``/chat/completions`` schema:
DeepSeek, Kimi, vLLM, SGLang, local gateways. Token usage is normalized
when the server returns it.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import ProviderError


class OpenAICompatibleProvider:
    """Thin adapter over OpenAI's SDK pointed at a configurable base URL."""

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int | None = None,
    ) -> None:
        if not base_url:
            raise ProviderError(
                "OPENAI_COMPATIBLE_BASE_URL is required for openai_compatible provider"
            )
        if not api_key:
            raise ProviderError(
                "OPENAI_COMPATIBLE_API_KEY is required for openai_compatible provider"
            )
        if not model:
            raise ProviderError(
                "OPENAI_COMPATIBLE_MODEL is required for openai_compatible provider"
            )
        self.provider_name = provider_name or "openai_compatible"
        self.model_name = model
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        self.last_usage: dict[str, int] = {}

    # --- LLMProvider protocol -----------------------------------------------
    def generate_text(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        except Exception as exc:
            raise ProviderError(
                f"{self.provider_name} call failed: {type(exc).__name__}"
            ) from exc
        content = (
            response.choices[0].message.content
            if response.choices and response.choices[0].message
            else None
        )
        if not content:
            raise ProviderError(
                f"{self.provider_name} returned empty or malformed content"
            )
        self.last_usage = _normalize_usage(response)
        return content


def _normalize_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for src, dest in (
        ("prompt_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
        ("cached_tokens", "cached_tokens"),
        ("cache_read_input_tokens", "cached_tokens"),
    ):
        val = getattr(usage, src, None)
        if val is None and isinstance(usage, dict):
            val = usage.get(src)
        if isinstance(val, int):
            out[dest] = val
    return out
