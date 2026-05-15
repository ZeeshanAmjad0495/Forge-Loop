"""#45/M5: external base-URL validation (SSRF defense)."""

import pytest

from app.services.url_safety import UnsafeURLError, validate_external_base_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434",
    "http://localhost:8080",
    "http://10.0.0.5:3000",
    "http://192.168.1.9",
    "https://cloud.langfuse.com",
    "https://api.deepseek.com",
])
def test_safe_urls_pass(url):
    assert validate_external_base_url(url, label="x") == url


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "http://metadata.google.internal/x",
    "http://169.254.1.1",                 # link-local
    "ftp://example.com",                  # bad scheme
    "http://public.example.com",          # plaintext to public host
    "not-a-url",
    "",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(UnsafeURLError):
        validate_external_base_url(url, label="x")


def test_insecure_override_allows_http_public():
    validate_external_base_url(
        "http://internal.svc", label="x", allow_insecure_http=True
    )
