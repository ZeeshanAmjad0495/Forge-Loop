"""C2: ObservabilityProvider abstraction with a Langfuse backend.

ForgeLoop is cloud-supported, not cloud-dependent. Observability follows the
same provider pattern as RepositoryProvider / SecretProvider:

- ``NoOpObservabilityProvider`` — the default; does nothing.
- ``LangfuseObservabilityProvider`` — emits an LLM *generation* to Langfuse
  for every recorded CostRecord (model, tokens, cost, metadata).

Hard guarantees:
- Observability NEVER breaks the request path. Every public call is wrapped
  so a missing SDK, missing creds, or a backend exception degrades to a
  silent no-op.
- The Langfuse secret key is resolved via the secret provider at runtime —
  never read from a committed file, never logged.
- Tests never hit the network: the Langfuse client is injectable, and the
  provider is a no-op unless explicitly configured.
"""

from __future__ import annotations

from typing import Protocol

from .. import config as _config
from . import secrets as _secrets


class ObservabilityProvider(Protocol):
    name: str

    def record_generation(
        self,
        *,
        name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        project_id: str,
        source_type: str,
        source_id: str,
        metadata: dict | None = None,
    ) -> None: ...


class NoOpObservabilityProvider:
    name = "noop"

    def record_generation(self, **_kwargs) -> None:
        return None


class LangfuseObservabilityProvider:
    """Langfuse backend.

    The client may be injected (tests). If not injected it is lazily
    constructed from the ``langfuse`` SDK; if the SDK is absent or the
    credentials are incomplete the provider stays a no-op forever.
    """

    name = "langfuse"

    def __init__(self, *, client=None) -> None:
        self._client = client
        self._client_resolved = client is not None
        self._disabled = False

    # -- client resolution -------------------------------------------------

    def _resolve_client(self):
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        secret_key = (
            _secrets.get_secret("LANGFUSE_SECRET_KEY")
            or _config.LANGFUSE_SECRET_KEY
            or ""
        ).strip()
        public_key = (_config.LANGFUSE_PUBLIC_KEY or "").strip()
        host = (_config.LANGFUSE_HOST or "").strip()
        if not (secret_key and public_key and host):
            self._client = None
            self._disabled = True
            return None
        try:
            from langfuse import Langfuse  # type: ignore

            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
        except Exception:
            # SDK missing or construction failed — degrade to no-op.
            self._client = None
            self._disabled = True
        return self._client

    # -- public API --------------------------------------------------------

    def record_generation(
        self,
        *,
        name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        project_id: str,
        source_type: str,
        source_id: str,
        metadata: dict | None = None,
    ) -> None:
        if self._disabled:
            return None
        client = self._resolve_client()
        if client is None:
            return None
        try:
            client.generation(
                name=name,
                model=model,
                usage={
                    "input": int(input_tokens),
                    "output": int(output_tokens),
                    "total": int(total_tokens),
                    "unit": "TOKENS",
                },
                metadata={
                    "provider": provider,
                    "project_id": project_id,
                    "source_type": source_type,
                    "source_id": source_id,
                    "estimated_cost_usd": float(cost_usd),
                    **(metadata or {}),
                },
            )
        except Exception:
            # Observability must never break the request path.
            return None


_PROVIDER: ObservabilityProvider | None = None


def get_observability_provider() -> ObservabilityProvider:
    """Return the active observability provider (cached).

    Langfuse only when ``LANGFUSE_ENABLED`` is true; otherwise no-op. The
    Langfuse provider itself further degrades to no-op if creds/SDK are
    absent, so enabling the flag without creds is still safe.
    """
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    if _config.LANGFUSE_ENABLED:
        _PROVIDER = LangfuseObservabilityProvider()
    else:
        _PROVIDER = NoOpObservabilityProvider()
    return _PROVIDER


def reset_observability_provider() -> None:
    """Test hook — clear the cached provider so config changes take effect."""
    global _PROVIDER
    _PROVIDER = None


def set_observability_provider(provider: ObservabilityProvider) -> None:
    """Test hook — inject a provider directly."""
    global _PROVIDER
    _PROVIDER = provider


__all__ = [
    "ObservabilityProvider",
    "NoOpObservabilityProvider",
    "LangfuseObservabilityProvider",
    "get_observability_provider",
    "reset_observability_provider",
    "set_observability_provider",
]
