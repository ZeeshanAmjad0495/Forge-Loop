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


def _patch_subtask(subtask_id: str, payload: dict):
    return client.patch(f"/subtasks/{subtask_id}", json=payload)


# ---------------------------------------------------------------------------
# Non-status field updates
# ---------------------------------------------------------------------------

def test_patch_subtask_updates_title():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]
    resp = _patch_subtask(subtask_id, {"title": "New title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"


def test_patch_subtask_updates_qa_required():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]
    resp = _patch_subtask(subtask_id, {"qa_required": True})
    assert resp.status_code == 200
    assert resp.json()["qa_required"] is True


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def test_patch_subtask_proposed_to_ready():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    subtask_id = data["subtasks"][0]["id"]
    resp = _patch_subtask(subtask_id, {"status": "ready"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_patch_subtask_full_lifecycle():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    sid = data["subtasks"][0]["id"]
    assert _patch_subtask(sid, {"status": "ready"}).status_code == 200
    assert _patch_subtask(sid, {"status": "in_progress"}).status_code == 200
    resp = _patch_subtask(sid, {"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_patch_subtask_noop_status_allowed():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    sid = data["subtasks"][0]["id"]
    resp = _patch_subtask(sid, {"status": "proposed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "proposed"


def test_patch_subtask_invalid_transition_returns_400():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    sid = data["subtasks"][0]["id"]
    resp = _patch_subtask(sid, {"status": "completed"})
    assert resp.status_code == 400
    assert "proposed" in resp.json()["detail"]
    assert "completed" in resp.json()["detail"]


def test_patch_subtask_blocked_to_ready():
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    sid = data["subtasks"][0]["id"]
    _patch_subtask(sid, {"status": "blocked"})
    resp = _patch_subtask(sid, {"status": "ready"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Subtasks have no dependency checks
# ---------------------------------------------------------------------------

def test_patch_subtask_no_dependency_check():
    """Subtasks do not enforce depends_on; status can move freely within allowed transitions."""
    project = _create_project()
    req = _create_requirement(project["id"])
    data = _decompose(req["id"])
    sid = data["subtasks"][0]["id"]
    # proposed -> ready works with no dependency concept
    resp = _patch_subtask(sid, {"status": "ready"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------

def test_patch_missing_subtask_returns_404():
    resp = _patch_subtask("does-not-exist", {"status": "ready"})
    assert resp.status_code == 404
