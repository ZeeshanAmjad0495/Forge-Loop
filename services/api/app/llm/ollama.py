"""Ollama LLM provider (Release 9, Task 54).

Calls a local Ollama server via its HTTP API. Designed for low-risk support
tasks (summaries, classification, compression, memory extraction). Tests
mock the HTTP layer; this module never opens a real connection during tests.
"""

from __future__ import annotations

import json
from typing import Any

from urllib import error as urllib_error
from urllib import request as urllib_request

from .. import config as _config
from ..services.url_safety import UnsafeURLError, validate_external_base_url
from .base import ProviderError


class OllamaProvider:
    provider_name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        self.model_name = model
        # H8: reject SSRF/metadata/link-local targets and plaintext http to
        # a non-local host before any request is made.
        try:
            validated = validate_external_base_url(
                base_url,
                label="OLLAMA_BASE_URL",
                allow_insecure_http=_config.ALLOW_INSECURE_LLM_HTTP,
            )
        except UnsafeURLError as exc:
            raise ProviderError(str(exc)) from exc
        self._base_url = validated.rstrip("/")
        self._timeout_seconds = timeout_seconds

    # --- HTTP -----------------------------------------------------------------
    def _post_json(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self._timeout_seconds) as resp:
                # H8: bound the read against a hostile/runaway endpoint.
                raw = resp.read(_config.LLM_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _config.LLM_MAX_RESPONSE_BYTES:
                raise ProviderError("Ollama response exceeded size cap")
            body = raw.decode("utf-8")
        except urllib_error.URLError as exc:
            raise ProviderError(
                f"Ollama call failed: {type(exc).__name__}"
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(
                f"Ollama call timed out: {type(exc).__name__}"
            ) from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Ollama returned malformed JSON: {exc}") from exc

    # --- LLMProvider protocol -----------------------------------------------
    def generate_text(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        data = self._post_json("/api/chat", payload)
        message = data.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            # /api/chat may also return top-level "response" for /api/generate-style calls
            content = data.get("response")
        if not content:
            raise ProviderError("Ollama returned empty or malformed content")
        return content

    # --- Health -------------------------------------------------------------
    def is_available(self) -> bool:
        url = f"{self._base_url}/api/tags"
        try:
            with urllib_request.urlopen(url, timeout=self._timeout_seconds) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False
