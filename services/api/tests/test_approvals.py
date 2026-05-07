from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_project() -> dict:
    return client.post("/projects", json={"name": "P", "description": "d"}).json()


def _create_approval(project_id: str, target_type: str = "dev_task", target_id: str = "t1") -> dict:
    resp = client.post("/approvals", json={
        "project_id": project_id,
        "target_type": target_type,
        "target_id": target_id,
    })
    assert resp.status_code == 201
    return resp.json()


def _decide(approval_id: str, status: str, feedback: str | None = None) -> dict:
    body: dict = {"status": status}
    if feedback:
        body["feedback"] = feedback
    resp = client.patch(f"/approvals/{approval_id}", json=body)
    return resp


# ---------------------------------------------------------------------------
# POST /approvals
# ---------------------------------------------------------------------------

def test_create_approval_returns_201_pending():
    project = _create_project()
    resp = client.post("/approvals", json={
        "project_id": project["id"],
        "target_type": "dev_task",
        "target_id": "abc123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["project_id"] == project["id"]
    assert data["target_type"] == "dev_task"
    assert data["target_id"] == "abc123"
    assert data["requested_by"] == "auth-disabled"
    assert data["decided_by"] is None
    assert data["decided_at"] is None


def test_create_approval_missing_project_returns_404():
    resp = client.post("/approvals", json={
        "project_id": "nonexistent",
        "target_type": "dev_task",
        "target_id": "t1",
    })
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/approvals
# ---------------------------------------------------------------------------

def test_list_project_approvals_returns_created_approval():
    project = _create_project()
    _create_approval(project["id"], target_id="t1")
    _create_approval(project["id"], target_id="t2")
    resp = client.get(f"/projects/{project['id']}/approvals")
    assert resp.status_code == 200
    ids = [a["target_id"] for a in resp.json()]
    assert "t1" in ids
    assert "t2" in ids


def test_list_project_approvals_missing_project_returns_404():
    resp = client.get("/projects/nonexistent/approvals")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /approvals/{id}
# ---------------------------------------------------------------------------

def test_get_approval_returns_200():
    project = _create_project()
    created = _create_approval(project["id"])
    resp = client.get(f"/approvals/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_approval_missing_returns_404():
    resp = client.get("/approvals/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /approvals/{id}
# ---------------------------------------------------------------------------

def test_decide_approval_approved():
    project = _create_project()
    approval = _create_approval(project["id"])
    resp = _decide(approval["id"], "approved")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["decided_by"] == "auth-disabled"
    assert data["decided_at"] is not None


def test_decide_approval_rejected():
    project = _create_project()
    approval = _create_approval(project["id"])
    resp = _decide(approval["id"], "rejected", feedback="Not ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["feedback"] == "Not ready"


def test_decide_approval_needs_revision():
    project = _create_project()
    approval = _create_approval(project["id"])
    resp = _decide(approval["id"], "needs_revision")
    assert resp.status_code == 200
    assert resp.json()["status"] == "needs_revision"


def test_decide_approval_invalid_status_returns_400():
    project = _create_project()
    approval = _create_approval(project["id"])
    resp = client.patch(f"/approvals/{approval['id']}", json={"status": "banana"})
    assert resp.status_code in (400, 422)


def test_decide_approval_after_final_state_returns_400():
    project = _create_project()
    approval = _create_approval(project["id"])
    _decide(approval["id"], "approved")
    resp = _decide(approval["id"], "rejected")
    assert resp.status_code == 400
    assert "finalized" in resp.json()["detail"]


def test_decide_approval_missing_returns_404():
    resp = _decide("does-not-exist", "approved")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit event written on decision
# ---------------------------------------------------------------------------

def test_decision_creates_audit_event():
    project = _create_project()
    approval = _create_approval(project["id"])
    _decide(approval["id"], "approved")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "approval_requested" in actions
    assert "approval_approved" in actions


def test_rejection_creates_audit_event():
    project = _create_project()
    approval = _create_approval(project["id"])
    _decide(approval["id"], "rejected")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "approval_rejected" for e in events)


def test_needs_revision_creates_audit_event():
    project = _create_project()
    approval = _create_approval(project["id"])
    _decide(approval["id"], "needs_revision")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "approval_needs_revision" for e in events)
