"""#45/H6: request body-size cap (JSON-bomb / memory-DoS defense)."""

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_h6_oversized_body_rejected_413(monkeypatch):
    monkeypatch.setattr(config, "MAX_REQUEST_BODY_BYTES", 500)
    big = {"name": "x" * 5000, "description": "y"}
    r = client.post("/projects", json=big)
    assert r.status_code == 413
    assert "too large" in r.text


def test_h6_normal_body_passes(monkeypatch):
    monkeypatch.setattr(config, "MAX_REQUEST_BODY_BYTES", 10_000_000)
    r = client.post("/projects", json={"name": "ok", "description": "d"})
    assert r.status_code in (200, 201)


def test_h6_health_unaffected():
    assert client.get("/health").status_code == 200


def test_m9_docs_enabled_in_non_production():
    # ENVIRONMENT defaults to "local" in tests -> schema/docs available.
    assert client.get("/openapi.json").status_code == 200
