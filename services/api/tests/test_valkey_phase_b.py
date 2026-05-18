"""Task 95 — Valkey/cache wired into provider rate-limit + runner dedupe.

Both off by default (non-breaking). Rate-limit fails OPEN on cache
error (a cache outage must never block a model call). DB/in-process
locks remain authoritative; the cache is never the source of truth.
No real Valkey/Redis (in-memory cache backend).
"""

import pytest

from app import config
from app.services.cache_provider import (
    reset_cache_provider,
    runner_dedupe_touch,
)
from app.services.model_routing import (
    RoutedProviderError,
    _check_provider_rate_limit,
)


def setup_function():
    reset_cache_provider()


def test_rate_limit_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(config, "PROVIDER_RATE_LIMIT_ENABLED", False)
    for _ in range(100):
        _check_provider_rate_limit("deepseek")  # never raises


def test_rate_limit_blocks_over_limit(monkeypatch):
    monkeypatch.setattr(config, "PROVIDER_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "PROVIDER_RATE_LIMIT_PER_MINUTE", 3)
    for _ in range(3):
        _check_provider_rate_limit("deepseek")
    with pytest.raises(RoutedProviderError, match="RATE_LIMITED"):
        _check_provider_rate_limit("deepseek")
    # Different provider has an independent window.
    _check_provider_rate_limit("ollama")


def test_rate_limit_fails_open_on_cache_error(monkeypatch):
    monkeypatch.setattr(config, "PROVIDER_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "PROVIDER_RATE_LIMIT_PER_MINUTE", 1)

    import app.services.model_routing as mr

    def _boom():
        raise RuntimeError("cache down")

    monkeypatch.setattr(
        "app.services.cache_provider.get_cache_provider", _boom
    )
    # Cache outage -> fail open (no raise) even past the limit.
    for _ in range(5):
        mr._check_provider_rate_limit("deepseek")


def test_runner_dedupe_disabled_returns_true(monkeypatch):
    monkeypatch.setattr(config, "RUNNER_DEDUPE_CACHE_ENABLED", False)
    assert runner_dedupe_touch("dt-1", "ws-1") is True
    assert runner_dedupe_touch("dt-1", "ws-1") is True  # no-op, no dedupe


def test_runner_dedupe_marks_duplicate(monkeypatch):
    monkeypatch.setattr(config, "RUNNER_DEDUPE_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "RUNNER_DEDUPE_TTL_SECONDS", 60)
    assert runner_dedupe_touch("dt-9", "ws-9") is True   # fresh
    assert runner_dedupe_touch("dt-9", "ws-9") is False  # duplicate seen
    assert runner_dedupe_touch("dt-9", "ws-other") is True  # diff key
