"""Task 79: local-first cache / ephemeral-state abstraction.

Valkey/Redis-compatible, but NEVER the source of truth. Durable records
stay in the repository providers (MongoDB local / Firestore cloud); this
layer only *accelerates*: ContextPack render cache, provider rate-limit /
budget counters, and runner locks (prevent duplicate execution of the
same task).

The default backend is :class:`InMemoryCacheProvider` — no dependency,
deterministic, used by every test. :class:`RedisCacheProvider` is
imported lazily and only when ``CACHE_PROVIDER`` selects it, so importing
this module never requires ``redis`` to be installed.
"""

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod

from .. import config as _config

_SUPPORTED = ("memory", "inmemory", "local", "redis", "valkey", "")


class CacheProvider(ABC):
    backend: str = "abstract"
    # True when a *selected* backend was unavailable and we degraded
    # (only happens under CACHE_FAIL_OPEN for non-critical cache).
    degraded: bool = False
    degraded_reason: str = ""

    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def increment(
        self, key: str, amount: int = 1, ttl_seconds: int | None = None
    ) -> int: ...

    @abstractmethod
    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        """Return an opaque token if the lock was acquired, else None."""

    @abstractmethod
    def release_lock(self, name: str, token: str) -> bool:
        """Release only if ``token`` still owns the lock."""

    @abstractmethod
    def health_check(self) -> dict: ...


class InMemoryCacheProvider(CacheProvider):
    """Process-local, monotonic-clock TTL. Deterministic; default."""

    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, tuple[str, float | None]] = {}
        self._locks: dict[str, tuple[str, float]] = {}

    def _alive(self, expiry: float | None) -> bool:
        return expiry is None or expiry > time.monotonic()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            value, expiry = item
            if not self._alive(expiry):
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        with self._lock:
            expiry = (
                time.monotonic() + ttl_seconds
                if ttl_seconds and ttl_seconds > 0
                else None
            )
            self._store[key] = (str(value), expiry)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def increment(
        self, key: str, amount: int = 1, ttl_seconds: int | None = None
    ) -> int:
        with self._lock:
            item = self._store.get(key)
            current = 0
            expiry: float | None = None
            if item is not None and self._alive(item[1]):
                try:
                    current = int(item[0])
                except (TypeError, ValueError):
                    current = 0
                expiry = item[1]
            new_val = current + amount
            if ttl_seconds and ttl_seconds > 0 and expiry is None:
                expiry = time.monotonic() + ttl_seconds
            self._store[key] = (str(new_val), expiry)
            return new_val

    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        with self._lock:
            held = self._locks.get(name)
            now = time.monotonic()
            if held is not None and held[1] > now:
                return None
            token = uuid.uuid4().hex
            self._locks[name] = (token, now + max(1, ttl_seconds))
            return token

    def release_lock(self, name: str, token: str) -> bool:
        with self._lock:
            held = self._locks.get(name)
            if held is not None and held[0] == token:
                self._locks.pop(name, None)
                return True
            return False

    def health_check(self) -> dict:
        return {
            "backend": self.backend,
            "healthy": True,
            "degraded": self.degraded,
        }


_RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


class RedisCacheProvider(CacheProvider):
    """Redis/Valkey backend. ``redis`` is imported here only."""

    backend = "redis"

    def __init__(self, *, url: str, connect_timeout_ms: int) -> None:
        import redis  # lazy: only when this backend is selected

        timeout_s = max(0.001, connect_timeout_ms / 1000.0)
        self._client = redis.Redis.from_url(
            url,
            socket_connect_timeout=timeout_s,
            socket_timeout=timeout_s,
            decode_responses=True,
        )
        # Fail fast at construction so the factory can apply the
        # fail-open / fail-fast policy deterministically.
        self._client.ping()

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if ttl_seconds and ttl_seconds > 0:
            self._client.set(key, value, ex=int(ttl_seconds))
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def increment(
        self, key: str, amount: int = 1, ttl_seconds: int | None = None
    ) -> int:
        pipe = self._client.pipeline()
        pipe.incrby(key, amount)
        if ttl_seconds and ttl_seconds > 0:
            pipe.expire(key, int(ttl_seconds), nx=True)
        result = pipe.execute()
        return int(result[0])

    def acquire_lock(self, name: str, ttl_seconds: int) -> str | None:
        token = uuid.uuid4().hex
        ok = self._client.set(
            f"lock:{name}",
            token,
            nx=True,
            px=int(max(1, ttl_seconds) * 1000),
        )
        return token if ok else None

    def release_lock(self, name: str, token: str) -> bool:
        try:
            res = self._client.eval(_RELEASE_LUA, 1, f"lock:{name}", token)
            return bool(res)
        except Exception:
            return False

    def health_check(self) -> dict:
        try:
            self._client.ping()
            return {"backend": self.backend, "healthy": True, "degraded": False}
        except Exception as exc:  # noqa: BLE001 - report, never raise
            return {
                "backend": self.backend,
                "healthy": False,
                "degraded": self.degraded,
                "error": type(exc).__name__,
            }


_singleton_lock = threading.Lock()
_instance: CacheProvider | None = None


def _build() -> CacheProvider:
    sel = (_config.CACHE_PROVIDER or "memory").strip().lower()
    if sel in ("memory", "inmemory", "local", ""):
        return InMemoryCacheProvider()
    if sel in ("redis", "valkey"):
        try:
            provider: CacheProvider = RedisCacheProvider(
                url=_config.CACHE_REDIS_URL,
                connect_timeout_ms=_config.CACHE_CONNECT_TIMEOUT_MS,
            )
            provider.backend = sel
            return provider
        except Exception as exc:  # noqa: BLE001 - policy decision below
            if _config.CACHE_FAIL_OPEN:
                fallback = InMemoryCacheProvider()
                fallback.degraded = True
                fallback.degraded_reason = (
                    f"{sel}_unavailable_fail_open:{type(exc).__name__}"
                )
                return fallback
            raise RuntimeError(
                f"CACHE_PROVIDER={sel} selected but the backend is "
                f"unavailable and CACHE_FAIL_OPEN=false "
                f"({type(exc).__name__})."
            ) from exc
    raise RuntimeError(
        f"Unsupported CACHE_PROVIDER={sel!r}. Supported: memory, redis, valkey"
    )


def get_cache_provider() -> CacheProvider:
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = _build()
    return _instance


def reset_cache_provider() -> None:
    """Drop the singleton (also clears in-memory state). Test/process hook."""
    global _instance
    with _singleton_lock:
        _instance = None


def require_rate_limit_backend() -> CacheProvider:
    """Cache for a *critical* rate-limit / budget counter path.

    The expensive-provider budget guard must not silently fail-open on a
    degraded cache. The authoritative guard still computes from durable
    CostRecords (see provider_budget.py); this only governs whether the
    cache may be *trusted* as an accelerator on that path.
    """
    provider = get_cache_provider()
    if provider.degraded and not _config.RATE_LIMIT_CACHE_FAIL_OPEN:
        raise RuntimeError(
            "Rate-limit cache is degraded and RATE_LIMIT_CACHE_FAIL_OPEN="
            "false: refusing to trust cache counters for the budget guard."
        )
    return provider


def cache_runtime_summary() -> dict:
    """Sanitized posture for GET /runtime/cache. No URL / no secrets."""
    provider = get_cache_provider()
    try:
        health = provider.health_check()
    except Exception as exc:  # noqa: BLE001
        health = {"healthy": False, "error": type(exc).__name__}
    return {
        "configured_provider": (_config.CACHE_PROVIDER or "memory"),
        "active_backend": provider.backend,
        "enabled": _config.CACHE_ENABLED,
        "default_ttl_seconds": _config.CACHE_DEFAULT_TTL_SECONDS,
        "fail_open": _config.CACHE_FAIL_OPEN,
        "rate_limit_fail_open": _config.RATE_LIMIT_CACHE_FAIL_OPEN,
        "degraded": provider.degraded,
        "degraded_reason": provider.degraded_reason,
        "is_source_of_truth": False,
        "health": health,
    }


__all__ = [
    "CacheProvider",
    "InMemoryCacheProvider",
    "RedisCacheProvider",
    "get_cache_provider",
    "reset_cache_provider",
    "require_rate_limit_backend",
    "cache_runtime_summary",
]
