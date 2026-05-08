from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REQUIREMENT_PAYLOAD = {
    "title": "Add feature",
    "problem_statement": "Users need X.",
    "business_goal": "Grow revenue.",
    "target_users": ["admins"],
    "functional_requirements": ["Do X"],
    "non_functional_requirements": [],
    "acceptance_criteria": ["X works"],
    "constraints": [],
    "non_goals": [],
    "assumptions": [],
}


def _create_project() -> dict:
    return client.post("/projects", json={"name": "P1", "description": "d"}).json()


def _create_requirement(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()


def _decompose(requirement_id: str) -> dict:
    return client.post(f"/requirements/{requirement_id}/task-decompositions").json()


def _create_epic(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/epics", json={"title": "Epic A"}
    ).json()


# ---------------------------------------------------------------------------
# DevTask assignment
# ---------------------------------------------------------------------------

def test_patch_dev_task_sets_epic_id():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    epic = _create_epic(project["id"])

    resp = client.patch(f"/dev-tasks/{task_id}", json={"epic_id": epic["id"]})
    assert resp.status_code == 200
    assert resp.json()["epic_id"] == epic["id"]


def test_patch_dev_task_sets_assignee_type_human():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]

    resp = client.patch(
        f"/dev-tasks/{task_id}",
        json={"assignee_type": "human", "assignee_name": "Bob", "assignee_id": "u-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assignee_type"] == "human"
    assert body["assignee_name"] == "Bob"
    assert body["assignee_id"] == "u-1"


def test_patch_dev_task_sets_assignee_type_agent():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]

    resp = client.patch(
        f"/dev-tasks/{task_id}",
        json={"assignee_type": "agent", "assignee_name": "gpt-agent"},
    )
    assert resp.status_code == 200
    assert resp.json()["assignee_type"] == "agent"


def test_patch_dev_task_assignment_does_not_change_status():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    original_status = data["dev_tasks"][0]["status"]

    resp = client.patch(
        f"/dev-tasks/{task_id}",
        json={"assignee_type": "human", "assignee_name": "Alice"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == original_status


def test_dev_task_assignment_emits_audit_event():
    from app.main import audit_event_repo
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]

    client.patch(
        f"/dev-tasks/{task_id}",
        json={"assignee_type": "human", "assignee_name": "Alice"},
    )
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "dev_task_assigned" in actions
    assigned_event = next(e for e in events if e.action == "dev_task_assigned")
    assert assigned_event.target_id == task_id
    assert "assignee_type" in assigned_event.details.get("changed_fields", [])


def test_dev_task_assignment_no_audit_event_on_noop():
    from app.main import audit_event_repo
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]

    # assignee_type is already "unassigned" by default — patching same value
    client.patch(f"/dev-tasks/{task_id}", json={"assignee_type": "unassigned"})
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "dev_task_assigned" not in actions


# ---------------------------------------------------------------------------
# Subtask assignment
# ---------------------------------------------------------------------------

def test_patch_subtask_sets_assignee_fields():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]

    resp = client.patch(
        f"/subtasks/{subtask_id}",
        json={"assignee_type": "agent", "assignee_name": "test-bot", "assignee_id": "a-1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assignee_type"] == "agent"
    assert body["assignee_name"] == "test-bot"
    assert body["assignee_id"] == "a-1"


def test_patch_subtask_assignment_does_not_change_status():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]
    original_status = data["subtasks"][0]["status"]

    resp = client.patch(
        f"/subtasks/{subtask_id}",
        json={"assignee_type": "human"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == original_status


def test_subtask_assignment_emits_audit_event():
    from app.main import audit_event_repo
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]

    client.patch(
        f"/subtasks/{subtask_id}",
        json={"assignee_type": "human", "assignee_name": "Carol"},
    )
    events = audit_event_repo.list_by_project(project["id"])
    actions = [e.action for e in events]
    assert "subtask_assigned" in actions
    assigned_event = next(e for e in events if e.action == "subtask_assigned")
    assert assigned_event.target_id == subtask_id


# ---------------------------------------------------------------------------
# Default values visible in responses
# ---------------------------------------------------------------------------

def test_dev_task_has_default_assignment_fields():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task = data["dev_tasks"][0]
    assert task["assignee_type"] == "unassigned"
    assert task["assignee_id"] is None
    assert task["assignee_name"] is None
    assert task["epic_id"] is None


def test_subtask_has_default_assignment_fields():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask = data["subtasks"][0]
    assert subtask["assignee_type"] == "unassigned"
    assert subtask["assignee_id"] is None
    assert subtask["assignee_name"] is None
