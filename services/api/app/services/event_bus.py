"""Task 80 (Phase A): EventBus abstraction + in-memory implementation.

Local-first event fanout. The in-memory bus is synchronous, dependency-
free, deterministic, and the default used by every test. A NATS adapter
is *designed for* but intentionally NOT implemented in Phase A — selecting
it fails fast with a clear message and never imports `nats`.

The bus is a notification channel only. It is NEVER the source of truth:
durable state stays in the repository providers and audit events. A
dropped/handled event must not lose durable data.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from .. import config as _config

EventHandler = Callable[[dict], None]

_SUPPORTED = ("memory", "inmemory", "local", "nats", "")


class EventBus(ABC):
    backend: str = "abstract"

    @abstractmethod
    def publish(
        self, event_type: str, payload: dict, *, project_id: str | None = None
    ) -> int:
        """Deliver to subscribers. Returns the number of handlers invoked."""

    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> None: ...

    @abstractmethod
    def health_check(self) -> dict: ...


class InMemoryEventBus(EventBus):
    """Synchronous in-process fanout. No durability (by design)."""

    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: dict[str, list[EventHandler]] = {}
        self._published: int = 0

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def publish(
        self, event_type: str, payload: dict, *, project_id: str | None = None
    ) -> int:
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
            self._published += 1
        event = {
            "event_type": event_type,
            "project_id": project_id,
            "payload": dict(payload or {}),
        }
        delivered = 0
        for handler in handlers:
            # One bad subscriber must not break fanout or the caller;
            # durable state is owned elsewhere, so a handler error here
            # is non-fatal and intentionally swallowed.
            try:
                handler(event)
                delivered += 1
            except Exception:
                continue
        return delivered

    def health_check(self) -> dict:
        with self._lock:
            return {
                "backend": self.backend,
                "healthy": True,
                "subscribed_event_types": sorted(self._handlers),
                "published_count": self._published,
            }


def _nats_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("nats") is not None


class NatsEventBus(EventBus):
    """Task 94 — NATS Phase B adapter (optional, config-gated).

    Selectable via ``EVENT_BUS_PROVIDER=nats``. A live NATS fanout needs
    the ``nats`` library AND a running NATS server — both out of scope
    here (tests must not need real NATS). So this adapter **always
    delegates to the local in-memory bus** while reporting whether
    ``nats`` is importable, so a later task can add the live publisher
    without changing call sites. Never the source of truth (durable
    state stays in repositories + the audit log).
    """

    def __init__(self) -> None:
        self._delegate = InMemoryEventBus()
        self._nats = _nats_available()
        self.backend = (
            "nats" if self._nats else "nats_unavailable_fallback_memory"
        )

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._delegate.subscribe(event_type, handler)

    def publish(
        self, event_type: str, payload: dict, *, project_id: str | None = None
    ) -> int:
        return self._delegate.publish(
            event_type, payload, project_id=project_id
        )

    def health_check(self) -> dict:
        h = self._delegate.health_check()
        h.update(
            {
                "backend": self.backend,
                "nats_importable": self._nats,
                "live_nats": False,
                "note": (
                    "Phase-B seam: delegates to the local in-memory bus; "
                    "live NATS publisher is a later task"
                ),
            }
        )
        return h


_singleton_lock = threading.Lock()
_instance: EventBus | None = None


def _build() -> EventBus:
    sel = (_config.EVENT_BUS_PROVIDER or "memory").strip().lower()
    if sel in ("memory", "inmemory", "local", ""):
        return InMemoryEventBus()
    if sel == "nats":
        return NatsEventBus()
    raise RuntimeError(
        f"Unsupported EVENT_BUS_PROVIDER={sel!r}. Supported: memory, nats"
    )


def get_event_bus() -> EventBus:
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = _build()
    return _instance


def reset_event_bus() -> None:
    """Drop the singleton (clears handlers). Test/process hook."""
    global _instance
    with _singleton_lock:
        _instance = None


def event_bus_runtime_summary() -> dict:
    bus = get_event_bus()
    try:
        health = bus.health_check()
    except Exception as exc:  # noqa: BLE001
        health = {"healthy": False, "error": type(exc).__name__}
    return {
        "configured_provider": (_config.EVENT_BUS_PROVIDER or "memory"),
        "active_backend": bus.backend,
        "is_source_of_truth": False,
        "nats_adapter": "phase_b_seam_in_memory_fallback",
        "health": health,
    }


__all__ = [
    "EventBus",
    "InMemoryEventBus",
    "NatsEventBus",
    "EventHandler",
    "get_event_bus",
    "reset_event_bus",
    "event_bus_runtime_summary",
]
