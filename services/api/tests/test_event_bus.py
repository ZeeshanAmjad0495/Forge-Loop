"""Task 80 Phase A: EventBus tests. No NATS required or imported."""

import sys

import pytest

from app import config
from app.services import event_bus as eb
from app.services.event_bus import InMemoryEventBus


def test_publish_no_subscribers_is_noop():
    bus = InMemoryEventBus()
    assert bus.publish("x.event", {"k": 1}) == 0


def test_subscribe_and_publish_delivers_event():
    bus = InMemoryEventBus()
    seen: list[dict] = []
    bus.subscribe("ticket.created", seen.append)
    n = bus.publish("ticket.created", {"id": "t1"}, project_id="p1")
    assert n == 1
    assert seen[0]["event_type"] == "ticket.created"
    assert seen[0]["project_id"] == "p1"
    assert seen[0]["payload"] == {"id": "t1"}


def test_multiple_handlers_all_invoked():
    bus = InMemoryEventBus()
    calls: list[str] = []
    bus.subscribe("e", lambda _ev: calls.append("a"))
    bus.subscribe("e", lambda _ev: calls.append("b"))
    assert bus.publish("e", {}) == 2
    assert sorted(calls) == ["a", "b"]


def test_handler_exception_is_isolated():
    bus = InMemoryEventBus()
    ok: list[int] = []

    def bad(_ev):
        raise RuntimeError("boom")

    bus.subscribe("e", bad)
    bus.subscribe("e", lambda _ev: ok.append(1))
    # One bad subscriber must not break fanout or the caller.
    assert bus.publish("e", {}) == 1
    assert ok == [1]


def test_factory_memory_default_and_reset(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_PROVIDER", "memory")
    eb.reset_event_bus()
    b1 = eb.get_event_bus()
    assert isinstance(b1, InMemoryEventBus)
    assert eb.get_event_bus() is b1  # singleton
    eb.reset_event_bus()
    assert eb.get_event_bus() is not b1


def test_nats_selection_falls_back_to_memory_without_import(monkeypatch):
    # Task 94: EVENT_BUS_PROVIDER=nats is now an optional Phase-B
    # adapter that degrades to the in-memory bus when nats is absent
    # (no hard fail, no nats import).
    assert "nats" not in sys.modules
    monkeypatch.setattr(config, "EVENT_BUS_PROVIDER", "nats")
    eb.reset_event_bus()
    bus = eb.get_event_bus()
    assert bus.backend == "nats_unavailable_fallback_memory"
    h = bus.health_check()
    assert h["nats_importable"] is False
    assert h["live_nats"] is False
    assert h["healthy"] is True
    assert "nats" not in sys.modules
    eb.reset_event_bus()


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_PROVIDER", "rabbitmq")
    eb.reset_event_bus()
    with pytest.raises(RuntimeError, match="Unsupported EVENT_BUS_PROVIDER"):
        eb.get_event_bus()


def test_runtime_summary(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_PROVIDER", "memory")
    eb.reset_event_bus()
    s = eb.event_bus_runtime_summary()
    assert s["active_backend"] == "memory"
    assert s["is_source_of_truth"] is False
    assert s["nats_adapter"] == "phase_b_seam_in_memory_fallback"
    assert s["health"]["healthy"] is True
