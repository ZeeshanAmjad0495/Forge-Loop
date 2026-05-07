from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REQUIREMENT_PAYLOAD = {
    "title": "Audit test req",
    "problem_statement": "Need audit trail.",
    "business_goal": "Governance.",
    "target_users": ["admins"],
    "functional_requirements": ["Track actions"],
    "non_functional_requirements": [],
    "acceptance_criteria": [],
    "constraints": [],
    "non_goals": [],
    "assumptions": [],
}


def _create_project() -> dict:
    return client.post("/projects", json={"name": "AuditP", "description": "d"}).json()


def _create_requirement(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()


def _decompose(requirement_id: str) -> dict:
    return client.post(f"/requirements/{requirement_id}/task-decompositions").json()


# ---------------------------------------------------------------------------
# GET /projects/{id}/audit-events
# ---------------------------------------------------------------------------

def test_list_audit_events_empty_initially():
    project = _create_project()
    resp = client.get(f"/projects/{project['id']}/audit-events")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_audit_events_missing_project_returns_404():
    resp = client.get("/projects/nonexistent/audit-events")
    assert resp.status_code == 404


def test_requirement_creation_writes_audit_event():
    project = _create_project()
    _create_requirement(project["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "requirement_created" for e in events)


def test_task_decomposition_writes_audit_event():
    project = _create_project()
    req = _create_requirement(project["id"])
    _decompose(req["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "requirement_created" in actions
    assert "task_decomposition_created" in actions


# ---------------------------------------------------------------------------
# GET /audit-events/{id}
# ---------------------------------------------------------------------------

def test_get_audit_event_by_id():
    project = _create_project()
    _create_requirement(project["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert len(events) >= 1
    event_id = events[0]["id"]
    resp = client.get(f"/audit-events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == event_id


def test_get_audit_event_missing_returns_404():
    resp = client.get("/audit-events/does-not-exist")
    assert resp.status_code == 404
