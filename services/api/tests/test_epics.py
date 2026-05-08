from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_project() -> dict:
    return client.post("/projects", json={"name": "P1", "description": "d"}).json()


def _create_requirement(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/requirements",
        json={"title": "R1", "problem_statement": "ps"},
    ).json()


def _create_epic(project_id: str, **kwargs) -> dict:
    payload = {"title": "Epic 1", **kwargs}
    return client.post(f"/projects/{project_id}/epics", json=payload)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_epic_returns_201():
    project = _create_project()
    resp = _create_epic(project["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Epic 1"
    assert body["project_id"] == project["id"]
    assert body["status"] == "proposed"
    assert body["priority"] == "medium"
    assert body["assignee_type"] == "unassigned"
    assert body["assignee_id"] is None
    assert body["assignee_name"] is None
    assert body["requirement_id"] is None
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_epic_with_all_fields():
    project = _create_project()
    resp = _create_epic(
        project["id"],
        description="desc",
        priority="high",
        sequence_order=2,
        acceptance_criteria=["AC1"],
        business_goal="BG",
        assignee_type="human",
        assignee_id="user-123",
        assignee_name="Alice",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["priority"] == "high"
    assert body["assignee_type"] == "human"
    assert body["assignee_name"] == "Alice"
    assert body["assignee_id"] == "user-123"
    assert body["acceptance_criteria"] == ["AC1"]


def test_create_epic_missing_project_returns_404():
    resp = client.post("/projects/no-such-project/epics", json={"title": "E"})
    assert resp.status_code == 404


def test_create_epic_with_requirement_id():
    project = _create_project()
    req = _create_requirement(project["id"])
    resp = _create_epic(project["id"], requirement_id=req["id"])
    assert resp.status_code == 201
    assert resp.json()["requirement_id"] == req["id"]


def test_create_epic_invalid_requirement_returns_404():
    project = _create_project()
    resp = _create_epic(project["id"], requirement_id="no-such-req")
    assert resp.status_code == 404


def test_create_epic_requirement_wrong_project_returns_404():
    project_a = _create_project()
    project_b = _create_project()
    req = _create_requirement(project_a["id"])
    resp = _create_epic(project_b["id"], requirement_id=req["id"])
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_project_epics():
    project = _create_project()
    _create_epic(project["id"], title="E1")
    _create_epic(project["id"], title="E2")
    resp = client.get(f"/projects/{project['id']}/epics")
    assert resp.status_code == 200
    ids = {e["title"] for e in resp.json()}
    assert {"E1", "E2"} <= ids


def test_list_project_epics_missing_project_returns_404():
    resp = client.get("/projects/no-such/epics")
    assert resp.status_code == 404


def test_list_requirement_epics():
    project = _create_project()
    req = _create_requirement(project["id"])
    _create_epic(project["id"], title="Linked", requirement_id=req["id"])
    _create_epic(project["id"], title="Free")
    resp = client.get(f"/requirements/{req['id']}/epics")
    assert resp.status_code == 200
    titles = [e["title"] for e in resp.json()]
    assert "Linked" in titles
    assert "Free" not in titles


def test_list_requirement_epics_missing_requirement_returns_404():
    resp = client.get("/requirements/no-such/epics")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------

def test_get_epic():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.get(f"/epics/{epic['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == epic["id"]


def test_get_epic_missing_returns_404():
    resp = client.get("/epics/no-such-epic")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

def test_patch_epic_updates_title():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.patch(f"/epics/{epic['id']}", json={"title": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"


def test_patch_epic_updates_status():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.patch(f"/epics/{epic['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_epic_updates_priority():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.patch(f"/epics/{epic['id']}", json={"priority": "low"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "low"


def test_patch_epic_updates_assignee():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.patch(
        f"/epics/{epic['id']}",
        json={"assignee_type": "agent", "assignee_name": "bot-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assignee_type"] == "agent"
    assert body["assignee_name"] == "bot-1"


def test_patch_epic_invalid_assignee_type_returns_422():
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    resp = client.patch(f"/epics/{epic['id']}", json={"assignee_type": "robot"})
    assert resp.status_code == 422


def test_patch_epic_missing_returns_404():
    resp = client.patch("/epics/no-such", json={"title": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_audit_epic_created():
    from app.main import audit_event_repo
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "epic_created" in actions
    created_event = next(e for e in events if e.action == "epic_created")
    assert created_event.target_id == epic["id"]


def test_audit_epic_updated():
    from app.main import audit_event_repo
    project = _create_project()
    epic = _create_epic(project["id"]).json()
    client.patch(f"/epics/{epic['id']}", json={"title": "New Title"})
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "epic_updated" in actions
    updated_event = next(e for e in events if e.action == "epic_updated")
    assert "title" in updated_event.details.get("changed_fields", [])
