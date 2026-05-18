"""Task 94 — NATS Phase B adapter + audit-driven local fan-out.

NATS adapter is optional/config-gated and falls back to the in-memory
bus (no nats dependency; tests offline). The audit log stays the source
of truth; publishing is best-effort and off by default.
"""

from app import config
from app.main import app
from app.services import event_bus as eb
from app.services.audit_writer import AuditWriter
from app.repositories import InMemoryAuditEventRepository


def test_nats_adapter_optional_fallback(monkeypatch):
    monkeypatch.setattr(config, "EVENT_BUS_PROVIDER", "nats")
    eb.reset_event_bus()
    bus = eb.get_event_bus()
    seen = []
    bus.subscribe("x", lambda e: seen.append(e))
    assert bus.publish("x", {"k": 1}, project_id="p1") == 1
    assert seen and seen[0]["payload"] == {"k": 1}
    eb.reset_event_bus()


def test_audit_publishes_when_enabled(monkeypatch):
    eb.reset_event_bus()
    monkeypatch.setattr(config, "EVENT_BUS_PUBLISH_ENABLED", True)
    bus = eb.get_event_bus()
    got = []
    bus.subscribe("workspace_created", lambda e: got.append(e))
    repo = InMemoryAuditEventRepository()
    AuditWriter(repo).write(
        "workspace_created", "workspace", "ws-1", project_id="p1"
    )
    # Source of truth persisted...
    assert len(repo.list_by_project("p1")) == 1
    # ...and best-effort fan-out delivered.
    assert len(got) == 1
    assert got[0]["payload"]["target_id"] == "ws-1"
    eb.reset_event_bus()


def test_audit_does_not_publish_by_default(monkeypatch):
    eb.reset_event_bus()
    monkeypatch.setattr(config, "EVENT_BUS_PUBLISH_ENABLED", False)
    bus = eb.get_event_bus()
    got = []
    bus.subscribe("workspace_created", lambda e: got.append(e))
    repo = InMemoryAuditEventRepository()
    AuditWriter(repo).write(
        "workspace_created", "workspace", "ws-2", project_id="p1"
    )
    assert len(repo.list_by_project("p1")) == 1  # still persisted
    assert got == []  # publish off by default
    eb.reset_event_bus()
