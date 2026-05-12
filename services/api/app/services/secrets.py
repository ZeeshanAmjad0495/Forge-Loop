"""Secret provider abstraction (Release 8, Task 44).

A minimal interface for resolving credentials from the local environment.
Only the ``env`` provider is implemented; the abstraction is here so future
providers (Secret Manager, Vault, etc.) can be added without touching call
sites. Provider implementations never log secret values; errors reference
the secret *name* only.
"""

from __future__ import annotations

import os
from typing import Protocol


class SecretMissingError(RuntimeError):
    """Raised when a required secret is not configured."""


class SecretProvider(Protocol):
    name: str

    def get(self, name: str) -> str | None: ...


class EnvSecretProvider:
    """Resolve secrets from process environment variables."""

    name = "env"

    def get(self, secret_name: str) -> str | None:
        value = os.environ.get(secret_name)
        if value is None or value == "":
            return None
        return value


_PROVIDER: SecretProvider = EnvSecretProvider()


def _resolve_provider() -> SecretProvider:
    """Return the active secret provider based on config.

    Only ``env`` is implemented; unknown providers raise to surface
    configuration errors at the call site.
    """
    from .. import config

    provider_name = (config.SECRET_PROVIDER or "env").strip().lower()
    if provider_name == "env":
        return _PROVIDER
    raise SecretMissingError(
        f"Unsupported SECRET_PROVIDER={provider_name!r}. Supported: env"
    )


def get_secret(name: str) -> str | None:
    """Return the secret value for ``name``, or None if not configured."""
    return _resolve_provider().get(name)


def require_secret(name: str, *, purpose: str) -> str:
    """Return a secret value, raising ``SecretMissingError`` if missing.

    The error message references the secret name and the human-readable
    purpose so operators know what to configure. The secret value itself
    is never included.
    """
    value = get_secret(name)
    if value is None:
        raise SecretMissingError(
            f"Required secret {name!r} is not configured (needed for: {purpose})."
        )
    return value


def redact_secret_value(value: str | None) -> str:
    """Return a redacted placeholder so secrets never reach logs/responses."""
    if not value:
        return ""
    return "***redacted***"


def provider_name() -> str:
    """Return the active provider name (e.g. ``'env'``)."""
    return _resolve_provider().name
