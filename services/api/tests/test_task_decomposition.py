from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
    "business_goal": "Improve data portability.",
    "target_users": ["paying customers"],
    "functional_requirements": ["Export tickets as CSV"],
    "non_functional_requirements": ["Export within 5 seconds"],
    "acceptance_criteria": ["CSV is RFC 4180 compliant"],
    "constraints": [],
    "non_goals": [],
    "assumptions": [],
}


def _create_project() -> dict:
    return client.post("/projects", json={"name": "P1", "description": "d"}).json()


def _create_requirement(project_id: str) -> dict:
    return client.post(f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD).json()


def _create_ticket(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/tickets",
        json={"title": "Fix bug", "description": "Something is broken"},
    ).json()


# ---------------------------------------------------------------------------
# POST /requirements/{id}/task-decompositions
# ---------------------------------------------------------------------------

def test_create_task_decomposition_for_requirement_returns_201():
    project = _create_project()
    req = _create_requirement(project["id"])
    response = client.post(f"/requirements/{req['id']}/task-decompositions")
    assert response.status_code == 201


def test_create_task_decomposition_response_structure():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    assert "agent_run" in data
    assert "artifact" in data
    assert "dev_tasks" in data
    assert "subtasks" in data


def test_create_task_decomposition_agent_run_fields():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    run = data["agent_run"]
    assert run["agent_type"] == "task_decomposition"
    assert run["provider"] == "mock"
    assert run["requirement_id"] == req["id"]
    assert run["ticket_id"] is None


def test_create_task_decomposition_artifact_type():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    artifact = data["artifact"]
    assert artifact["artifact_type"] == "task_decomposition"
    assert artifact["requirement_id"] == req["id"]
    assert artifact["ticket_id"] is None


def test_create_task_decomposition_dev_tasks_non_empty():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    assert len(data["dev_tasks"]) >= 1
    for dt in data["dev_tasks"]:
        assert "id" in dt
        assert "title" in dt
        assert "qa_required" in dt
        assert isinstance(dt["depends_on"], list)


def test_create_task_decomposition_subtasks_linked_to_dev_tasks():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    dev_task_ids = {dt["id"] for dt in data["dev_tasks"]}
    for st in data["subtasks"]:
        assert st["dev_task_id"] in dev_task_ids


def test_create_task_decomposition_with_explicit_mock_provider():
    project = _create_project()
    req = _create_requirement(project["id"])
    response = client.post(
        f"/requirements/{req['id']}/task-decompositions",
        json={"provider": "mock"},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"


def test_create_task_decomposition_missing_requirement_404():
    response = client.post("/requirements/nope/task-decompositions")
    assert response.status_code == 404


def test_create_task_decomposition_unknown_provider_400():
    project = _create_project()
    req = _create_requirement(project["id"])
    response = client.post(
        f"/requirements/{req['id']}/task-decompositions",
        json={"provider": "gemini"},
    )
    assert response.status_code == 400


def test_create_task_decomposition_after_analysis():
    project = _create_project()
    req = _create_requirement(project["id"])
    # run analysis first so latest_analysis is available
    client.post(f"/requirements/{req['id']}/requirement-analyses")
    response = client.post(f"/requirements/{req['id']}/task-decompositions")
    assert response.status_code == 201
    data = response.json()
    assert len(data["dev_tasks"]) >= 1


# ---------------------------------------------------------------------------
# POST /tickets/{id}/task-decompositions
# ---------------------------------------------------------------------------

def test_create_task_decomposition_for_ticket_returns_201():
    project = _create_project()
    ticket = _create_ticket(project["id"])
    response = client.post(f"/tickets/{ticket['id']}/task-decompositions")
    assert response.status_code == 201


def test_create_task_decomposition_for_ticket_response_structure():
    project = _create_project()
    ticket = _create_ticket(project["id"])
    data = client.post(f"/tickets/{ticket['id']}/task-decompositions").json()
    assert "agent_run" in data
    assert "dev_tasks" in data
    assert "subtasks" in data
    assert data["agent_run"]["agent_type"] == "task_decomposition"
    assert data["agent_run"]["ticket_id"] == ticket["id"]


def test_create_task_decomposition_for_ticket_missing_404():
    response = client.post("/tickets/nope/task-decompositions")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/dev-tasks
# ---------------------------------------------------------------------------

def test_list_project_dev_tasks_returns_tasks():
    project = _create_project()
    req = _create_requirement(project["id"])
    client.post(f"/requirements/{req['id']}/task-decompositions")
    response = client.get(f"/projects/{project['id']}/dev-tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) >= 1
    assert all(t["project_id"] == project["id"] for t in tasks)


def test_list_project_dev_tasks_missing_project_404():
    response = client.get("/projects/nope/dev-tasks")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /dev-tasks/{id}
# ---------------------------------------------------------------------------

def test_get_dev_task_returns_task_with_subtasks():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    dev_task_id = data["dev_tasks"][0]["id"]
    response = client.get(f"/dev-tasks/{dev_task_id}")
    assert response.status_code == 200
    body = response.json()
    assert "dev_task" in body
    assert "subtasks" in body
    assert body["dev_task"]["id"] == dev_task_id


def test_get_dev_task_missing_404():
    response = client.get("/dev-tasks/nope")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /dev-tasks/{id}/subtasks
# ---------------------------------------------------------------------------

def test_list_dev_task_subtasks_returns_list():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    dev_task_id = data["dev_tasks"][0]["id"]
    response = client.get(f"/dev-tasks/{dev_task_id}/subtasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_dev_task_subtasks_missing_dev_task_404():
    response = client.get("/dev-tasks/nope/subtasks")
    assert response.status_code == 404
