from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_ticket_returns_201():
    response = client.post("/tickets", json={"title": "Fix login", "description": "Login fails on mobile"})
    assert response.status_code == 201


def test_create_ticket_response_shape():
    response = client.post("/tickets", json={"title": "Fix login", "description": "Login fails on mobile"})
    data = response.json()
    assert data["title"] == "Fix login"
    assert data["description"] == "Login fails on mobile"
    assert data["status"] == "created"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_ticket_returns_created_ticket():
    created = client.post("/tickets", json={"title": "Fix login", "description": "Login fails on mobile"}).json()
    response = client.get(f"/tickets/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_ticket_returns_404():
    response = client.get("/tickets/nonexistent-id")
    assert response.status_code == 404
