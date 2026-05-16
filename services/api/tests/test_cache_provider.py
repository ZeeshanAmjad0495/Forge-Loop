"""Task 79: cache / ephemeral-state abstraction tests.

All deterministic and run WITHOUT Redis installed or running.
"""

import sys

import pytest

from app import config
from app.services import cache_provider as cpmod
from app.services.cache_provider import InMemoryCacheProvider
from app.services.contextpack_builder import (
    ContextPackBuildRequest,
    build_context_pack,
)


# 1. In-memory get/set/delete.
def test_inmemory_get_set_delete():
    p = InMemoryCacheProvider()
    assert p.get("missing") is None
    p.set("k", "v")
    assert p.get("k") == "v"
    p.delete("k")
    assert p.get("k") is None


# 2. TTL expiry (fake monotonic clock — deterministic).
def test_inmemory_ttl_expiry(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(cpmod.time, "monotonic", lambda: clock["t"])
    p = InMemoryCacheProvider()
    p.set("k", "v", ttl_seconds=10)
    assert p.get("k") == "v"
    clock["t"] += 11
    assert p.get("k") is None


# 3. increment with and without ttl.
def test_inmemory_increment():
    p = InMemoryCacheProvider()
    assert p.increment("c") == 1
    assert p.increment("c", 2) == 3
    assert p.increment("c", ttl_seconds=60) == 4
    assert p.get("c") == "4"


# 4. lock acquire/release semantics.
def test_inmemory_lock():
    p = InMemoryCacheProvider()
    t1 = p.acquire_lock("task:1", 30)
    assert t1
    assert p.acquire_lock("task:1", 30) is None
    assert p.release_lock("task:1", "wrong-token") is False
    assert p.release_lock("task:1", t1) is True
    assert p.acquire_lock("task:1", 30)


# 5. lock auto-expires.
def test_inmemory_lock_expiry(monkeypatch):
    clock = {"t": 500.0}
    monkeypatch.setattr(cpmod.time, "monotonic", lambda: clock["t"])
    p = InMemoryCacheProvider()
    assert p.acquire_lock("L", 5)
    assert p.acquire_lock("L", 5) is None
    clock["t"] += 6
    assert p.acquire_lock("L", 5)


# 6. health_check.
def test_inmemory_health():
    h = InMemoryCacheProvider().health_check()
    assert h["backend"] == "memory"
    assert h["healthy"] is True


# 7. Factory returns InMemory for memory and never imports redis.
def test_factory_memory_no_redis(monkeypatch):
    assert "redis" not in sys.modules  # not a project dependency
    monkeypatch.setattr(config, "CACHE_PROVIDER", "memory")
    cpmod.reset_cache_provider()
    prov = cpmod.get_cache_provider()
    assert isinstance(prov, InMemoryCacheProvider)
    assert prov.degraded is False
    assert "redis" not in sys.modules


# 8. Redis selected but unavailable + CACHE_FAIL_OPEN=true -> degrade.
def test_factory_redis_unavailable_fail_open(monkeypatch):
    monkeypatch.setattr(config, "CACHE_PROVIDER", "redis")
    monkeypatch.setattr(config, "CACHE_FAIL_OPEN", True)
    cpmod.reset_cache_provider()
    prov = cpmod.get_cache_provider()
    assert isinstance(prov, InMemoryCacheProvider)
    assert prov.degraded is True
    assert "unavailable_fail_open" in prov.degraded_reason


# 9. Redis selected but unavailable + CACHE_FAIL_OPEN=false -> fail fast.
def test_factory_redis_unavailable_fail_fast(monkeypatch):
    monkeypatch.setattr(config, "CACHE_PROVIDER", "valkey")
    monkeypatch.setattr(config, "CACHE_FAIL_OPEN", False)
    cpmod.reset_cache_provider()
    with pytest.raises(RuntimeError, match="CACHE_FAIL_OPEN=false"):
        cpmod.get_cache_provider()


# 10. Unknown provider -> fail fast (factory + startup validation).
def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(config, "CACHE_PROVIDER", "weird")
    cpmod.reset_cache_provider()
    with pytest.raises(RuntimeError, match="Unsupported CACHE_PROVIDER"):
        cpmod.get_cache_provider()
    monkeypatch.setattr(config, "FORGELOOP_ALLOW_NO_AUTH", True)
    with pytest.raises(RuntimeError, match="CACHE_PROVIDER"):
        config.validate_startup_config()


# 11. Critical rate-limit path must not trust a degraded cache.
def test_require_rate_limit_backend(monkeypatch):
    monkeypatch.setattr(config, "CACHE_PROVIDER", "redis")
    monkeypatch.setattr(config, "CACHE_FAIL_OPEN", True)
    monkeypatch.setattr(config, "RATE_LIMIT_CACHE_FAIL_OPEN", False)
    cpmod.reset_cache_provider()
    with pytest.raises(RuntimeError, match="RATE_LIMIT_CACHE_FAIL_OPEN"):
        cpmod.require_rate_limit_backend()
    monkeypatch.setattr(config, "RATE_LIMIT_CACHE_FAIL_OPEN", True)
    assert cpmod.require_rate_limit_backend() is not None


# 12. Runtime summary is sanitized (no URL / secret) and marks not-truth.
def test_cache_runtime_summary(monkeypatch):
    monkeypatch.setattr(config, "CACHE_PROVIDER", "memory")
    cpmod.reset_cache_provider()
    s = cpmod.cache_runtime_summary()
    assert s["active_backend"] == "memory"
    assert s["is_source_of_truth"] is False
    assert s["health"]["healthy"] is True
    assert config.CACHE_REDIS_URL not in str(s)
    assert "url" not in {k.lower() for k in s}


# 13. ContextPack build uses the cache abstraction (2nd build served fast).
def test_contextpack_uses_cache_abstraction(monkeypatch, client):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    monkeypatch.setattr(config, "CONTEXTPACK_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "CACHE_PROVIDER", "memory")
    cpmod.reset_cache_provider()
    pr = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    body = ContextPackBuildRequest(
        active_task_context="deterministic content",
        source_type="manual",
        source_id="s1",
        source_ids=["a"],
    )
    r1 = build_context_pack(project_id=pr["id"], body=body)
    assert r1.cached is False
    r2 = build_context_pack(project_id=pr["id"], body=body)
    assert r2.cached is True
    assert r1.estimated_tokens == r2.estimated_tokens


# 14. /runtime/cache route is reachable and sanitized.
def test_runtime_cache_route(client):
    res = client.get("/runtime/cache")
    assert res.status_code == 200
    data = res.json()
    assert data["active_backend"] in ("memory", "redis")
    assert data["is_source_of_truth"] is False
