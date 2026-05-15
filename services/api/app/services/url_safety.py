"""#45/M5+H8: shared external base-URL validation (SSRF defense).

Operator-configured base URLs that carry prompts/credentials (Ollama,
OpenHands bridge, Kody, OpenAI-compatible) must not silently point
ForgeLoop at cloud metadata / link-local / internal endpoints, nor send
secrets over plaintext HTTP to a non-loopback host.

This validates a *configured* base URL (not per-request input). It does
NOT perform DNS resolution — that would require network in tests and
gives false assurance against DNS rebinding; instead it blocks dangerous
literal hosts and enforces TLS for non-loopback/private targets.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOST_LITERALS = {
    "169.254.169.254",          # AWS/GCP/Azure IMDS
    "metadata.google.internal",
    "metadata",
    "100.100.100.200",          # Alibaba metadata
}


class UnsafeURLError(ValueError):
    """Raised when a configured external base URL is unsafe."""


def validate_external_base_url(
    url: str,
    *,
    label: str = "base URL",
    allow_insecure_http: bool = False,
) -> str:
    """Return the URL unchanged if safe; raise UnsafeURLError otherwise.

    - scheme must be http/https
    - host must be present and not a known metadata/link-local literal
    - non-loopback/non-private hosts must use https unless
      ``allow_insecure_http`` (operator escape hatch) is set
    """
    if not url or not isinstance(url, str):
        raise UnsafeURLError(f"{label} is empty")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(
            f"{label} must use http/https (got {parsed.scheme!r})"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeURLError(f"{label} has no host")
    if host in _BLOCKED_HOST_LITERALS:
        raise UnsafeURLError(
            f"{label} points at a blocked metadata/link-local host"
        )

    # Parse a literal IP separately so a parse failure (= hostname) never
    # swallows a policy rejection (UnsafeURLError is a ValueError subclass).
    ip: ipaddress._BaseAddress | None
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None

    if ip is not None:
        if (
            ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeURLError(
                f"{label} points at a link-local/reserved address"
            )
        if ip.is_loopback or ip.is_private:
            return url  # local/private literal — allowed (incl. http)
        if parsed.scheme != "https" and not allow_insecure_http:
            raise UnsafeURLError(
                f"{label} must use https for the public host {host!r}"
            )
        return url

    # Hostname (not a literal IP).
    if host == "localhost" or host.endswith(".localhost"):
        return url
    if parsed.scheme != "https" and not allow_insecure_http:
        raise UnsafeURLError(
            f"{label} must use https for the non-local host {host!r} "
            "(set the insecure-http override only for trusted internal "
            "endpoints)"
        )
    return url


__all__ = ["UnsafeURLError", "validate_external_base_url"]
