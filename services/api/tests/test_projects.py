from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_project_returns_201_and_shape():
    response = client.post(
        "/projects",
        json={"name": "ForgeLoop", "description": "Meta project", "tech_stack": ["python", "react"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "ForgeLoop"
    assert data["description"] == "Meta project"
    assert data["status"] == "active"
    assert data["tech_stack"] == ["python", "react"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_with_optional_fields():
    response = client.post(
        "/projects",
        json={"name": "Minimal", "description": "No extras"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["repo_url"] is None
    assert data["tech_stack"] == []


def test_list_projects_returns_created_projects():
    client.post("/projects", json={"name": "Alpha", "description": "First"})
    client.post("/projects", json={"name": "Beta", "description": "Second"})
    response = client.get("/projects")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_get_project_returns_project():
    created = client.post("/projects", json={"name": "Gamma", "description": "Third"}).json()
    response = client.get(f"/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_project_returns_404():
    response = client.get("/projects/nonexistent-project-id")
    assert response.status_code == 404


def test_get_context_returns_defaults_when_unset():
    project = client.post("/projects", json={"name": "CtxTest", "description": "For context"}).json()
    response = client.get(f"/projects/{project['id']}/context")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["architecture_notes"] == ""
    assert data["coding_standards"] == ""
    assert data["updated_at"] is None


def test_put_context_saves_and_returns():
    project = client.post("/projects", json={"name": "CtxSave", "description": "Save context"}).json()
    put_response = client.put(
        f"/projects/{project['id']}/context",
        json={"architecture_notes": "Hexagonal", "coding_standards": "PEP8"},
    )
    assert put_response.status_code == 200
    data = put_response.json()
    assert data["architecture_notes"] == "Hexagonal"
    assert data["coding_standards"] == "PEP8"
    assert data["updated_at"] is not None

    get_response = client.get(f"/projects/{project['id']}/context")
    assert get_response.json()["architecture_notes"] == "Hexagonal"


def test_put_context_unknown_project_returns_404():
    response = client.put(
        "/projects/nonexistent-project-id/context",
        json={"architecture_notes": "test"},
    )
    assert response.status_code == 404


def test_create_project_ticket_returns_201_and_links_project():
    project = client.post("/projects", json={"name": "TicketProject", "description": "Has tickets"}).json()
    response = client.post(
        f"/projects/{project['id']}/tickets",
        json={"title": "Add login", "description": "Users need to log in"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["status"] == "created"
    assert "id" in data


def test_create_project_ticket_unknown_project_returns_404():
    response = client.post(
        "/projects/nonexistent-id/tickets",
        json={"title": "X", "description": "Y"},
    )
    assert response.status_code == 404


def test_list_project_tickets_returns_only_that_projects_tickets():
    proj_a = client.post("/projects", json={"name": "A", "description": "Project A"}).json()
    proj_b = client.post("/projects", json={"name": "B", "description": "Project B"}).json()
    client.post(f"/projects/{proj_a['id']}/tickets", json={"title": "A1", "description": "Ticket in A"})
    client.post(f"/projects/{proj_a['id']}/tickets", json={"title": "A2", "description": "Second in A"})
    client.post(f"/projects/{proj_b['id']}/tickets", json={"title": "B1", "description": "Ticket in B"})

    resp_a = client.get(f"/projects/{proj_a['id']}/tickets")
    resp_b = client.get(f"/projects/{proj_b['id']}/tickets")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    titles_a = [t["title"] for t in resp_a.json()]
    titles_b = [t["title"] for t in resp_b.json()]
    assert sorted(titles_a) == ["A1", "A2"]
    assert titles_b == ["B1"]


def test_planning_run_for_project_ticket_includes_context():
    project = client.post("/projects", json={"name": "CtxPromptProject", "description": "Tests context injection"}).json()
    client.put(
        f"/projects/{project['id']}/context",
        json={"architecture_notes": "SENTINEL_ARCH_VALUE", "coding_standards": ""},
    )
    ticket = client.post(
        f"/projects/{project['id']}/tickets",
        json={"title": "Build feature X", "description": "Details of feature X"},
    ).json()
    response = client.post(f"/tickets/{ticket['id']}/planning-runs", json={})
    assert response.status_code == 201
    data = response.json()
    assert data["agent_run"]["status"] == "completed"
    assert data["artifact"]["artifact_type"] == "implementation_brief"
