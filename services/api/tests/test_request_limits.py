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


# --- #45/M8: unhandled errors must not leak internal detail --------------


def test_m8_unhandled_error_returns_opaque_500(monkeypatch):
    from app import repositories_state

    secret_ish = "/srv/secret/path connstr=mongodb://u:p@host"

    def boom(_id):
        raise RuntimeError(secret_ish)

    monkeypatch.setattr(repositories_state.project_repo, "get", boom)
    safe_client = TestClient(app, raise_server_exceptions=False)
    r = safe_client.get("/projects/anything")
    assert r.status_code == 500
    assert r.json() == {"detail": "internal server error"}
    assert secret_ish not in r.text
