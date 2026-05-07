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
    return client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()


def _decompose(requirement_id: str) -> dict:
    return client.post(
        f"/requirements/{requirement_id}/task-decompositions"
    ).json()


def _first_task(requirement_id: str) -> dict:
    project_id = client.get(f"/requirements/{requirement_id}").json()["project_id"]
    tasks = client.get(f"/projects/{project_id}/dev-tasks").json()
    return tasks[0]


def _patch_task(task_id: str, payload: dict) -> dict:
    return client.patch(f"/dev-tasks/{task_id}", json=payload)


# ---------------------------------------------------------------------------
# Non-status field updates
# ---------------------------------------------------------------------------

def test_patch_dev_task_updates_title():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    resp = _patch_task(task_id, {"title": "Updated title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


def test_patch_dev_task_updates_priority():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    resp = _patch_task(task_id, {"priority": "high"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "high"


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def test_patch_dev_task_proposed_to_ready():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    # pick a task with no depends_on
    task = next(t for t in data["dev_tasks"] if not t["depends_on"])
    resp = _patch_task(task["id"], {"status": "ready"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_patch_dev_task_ready_to_in_progress():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task = next(t for t in data["dev_tasks"] if not t["depends_on"])
    _patch_task(task["id"], {"status": "ready"})
    resp = _patch_task(task["id"], {"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_dev_task_in_progress_to_completed():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task = next(t for t in data["dev_tasks"] if not t["depends_on"])
    _patch_task(task["id"], {"status": "ready"})
    _patch_task(task["id"], {"status": "in_progress"})
    resp = _patch_task(task["id"], {"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_patch_dev_task_completed_to_in_progress_reopen():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task = next(t for t in data["dev_tasks"] if not t["depends_on"])
    _patch_task(task["id"], {"status": "ready"})
    _patch_task(task["id"], {"status": "in_progress"})
    _patch_task(task["id"], {"status": "completed"})
    resp = _patch_task(task["id"], {"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_dev_task_noop_status_allowed():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    resp = _patch_task(task_id, {"status": "proposed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "proposed"


def test_patch_dev_task_invalid_transition_returns_400():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    resp = _patch_task(task_id, {"status": "completed"})
    assert resp.status_code == 400
    assert "proposed" in resp.json()["detail"]
    assert "completed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Dependency readiness
# ---------------------------------------------------------------------------

def test_patch_dev_task_blocked_by_uncompleted_dependency():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_a = next(t for t in data["dev_tasks"] if not t["depends_on"])
    task_b = next(t for t in data["dev_tasks"] if t["id"] != task_a["id"])

    # Set task_b to depend on task_a (which is still 'proposed')
    _patch_task(task_b["id"], {"depends_on": [task_a["id"]]})

    resp = _patch_task(task_b["id"], {"status": "ready"})
    assert resp.status_code == 400
    assert "dependencies not completed" in resp.json()["detail"]


def test_patch_dev_task_ready_when_dependency_completed():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_a = next(t for t in data["dev_tasks"] if not t["depends_on"])
    task_b = next(t for t in data["dev_tasks"] if t["id"] != task_a["id"])

    # Complete task_a
    _patch_task(task_a["id"], {"status": "ready"})
    _patch_task(task_a["id"], {"status": "in_progress"})
    _patch_task(task_a["id"], {"status": "completed"})

    # Set task_b to depend on completed task_a
    _patch_task(task_b["id"], {"depends_on": [task_a["id"]]})

    resp = _patch_task(task_b["id"], {"status": "ready"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_patch_dev_task_in_progress_blocked_by_uncompleted_dep():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_a = next(t for t in data["dev_tasks"] if not t["depends_on"])
    task_b = next(t for t in data["dev_tasks"] if t["id"] != task_a["id"])

    # task_b may already have deps; clear them so we can reach 'ready'
    _patch_task(task_b["id"], {"depends_on": []})
    assert _patch_task(task_b["id"], {"status": "ready"}).status_code == 200

    # Now add a dep on task_a which is still 'proposed' (not completed)
    _patch_task(task_b["id"], {"depends_on": [task_a["id"]]})

    # Attempt to move task_b from 'ready' to 'in_progress' — must fail
    resp = _patch_task(task_b["id"], {"status": "in_progress"})
    assert resp.status_code == 400
    assert "dependencies not completed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------

def test_patch_missing_dev_task_returns_404():
    resp = _patch_task("does-not-exist", {"status": "ready"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Readiness fields on GET
# ---------------------------------------------------------------------------

def test_get_dev_task_includes_is_ready_and_blocked_by():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    task_id = data["dev_tasks"][0]["id"]
    resp = client.get(f"/dev-tasks/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "is_ready" in body["dev_task"]
    assert "blocked_by" in body["dev_task"]


def test_list_project_dev_tasks_includes_readiness():
    project = _create_project()
    req = _create_requirement(project["id"])
    _decompose(req["id"])
    resp = client.get(f"/projects/{project['id']}/dev-tasks")
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) >= 1
    assert "is_ready" in tasks[0]
    assert "blocked_by" in tasks[0]
