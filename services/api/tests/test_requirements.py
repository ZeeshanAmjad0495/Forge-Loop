from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


REQUIREMENT_PAYLOAD = {
    "title": "CSV export",
    "problem_statement": "Users have no way to export their data.",
    "business_goal": "Improve data portability for paying customers.",
    "target_users": ["paying customers"],
    "functional_requirements": [
        "Export tickets as CSV",
        "Allow date-range filter",
    ],
    "non_functional_requirements": ["Export within 5 seconds for 10k rows"],
    "acceptance_criteria": ["CSV file is RFC 4180 compliant"],
    "constraints": ["Must run in current Cloud Run service"],
    "non_goals": ["Excel formula support"],
    "assumptions": ["Existing auth covers this endpoint"],
}


def _create_project() -> dict:
    return client.post("/projects", json={"name": "P1", "description": "d"}).json()


# ---------------------------------------------------------------------------
# Create / list / get / update
# ---------------------------------------------------------------------------


def test_create_requirement_returns_201():
    project = _create_project()
    response = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["title"] == REQUIREMENT_PAYLOAD["title"]
    assert body["functional_requirements"] == REQUIREMENT_PAYLOAD["functional_requirements"]
    assert body["status"] == "draft"
    assert body["source"] == "manual"
    assert "id" in body


def test_create_requirement_missing_project_404():
    response = client.post("/projects/nope/requirements", json=REQUIREMENT_PAYLOAD)
    assert response.status_code == 404


def test_list_requirements_returns_only_for_project():
    p1 = _create_project()
    p2 = _create_project()
    client.post(f"/projects/{p1['id']}/requirements", json=REQUIREMENT_PAYLOAD)
    client.post(f"/projects/{p1['id']}/requirements", json=REQUIREMENT_PAYLOAD)
    client.post(f"/projects/{p2['id']}/requirements", json=REQUIREMENT_PAYLOAD)

    response = client.get(f"/projects/{p1['id']}/requirements")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert all(item["project_id"] == p1["id"] for item in items)


def test_list_requirements_missing_project_404():
    response = client.get("/projects/nope/requirements")
    assert response.status_code == 404


def test_get_requirement_returns_200():
    project = _create_project()
    created = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()
    response = client.get(f"/requirements/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_requirement_missing_404():
    response = client.get("/requirements/nope")
    assert response.status_code == 404


def test_update_requirement_changes_fields_and_preserves_invariants():
    project = _create_project()
    created = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()

    new_payload = {
        "title": "CSV export v2",
        "problem_statement": "Updated.",
        "business_goal": "Updated goal.",
        "target_users": ["enterprise"],
        "functional_requirements": ["Export as CSV", "Export as CSV with header"],
        "non_functional_requirements": [],
        "acceptance_criteria": ["Header row matches schema"],
        "constraints": [],
        "non_goals": [],
        "assumptions": [],
        "status": "ready_for_analysis",
    }
    response = client.put(f"/requirements/{created['id']}", json=new_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["project_id"] == created["project_id"]
    assert body["created_at"] == created["created_at"]
    assert body["source"] == created["source"]
    assert body["title"] == "CSV export v2"
    assert body["status"] == "ready_for_analysis"
    assert body["target_users"] == ["enterprise"]
    assert body["updated_at"] >= created["updated_at"]


def test_update_requirement_missing_404():
    response = client.put(
        "/requirements/nope",
        json={
            "title": "x",
            "problem_statement": "",
            "business_goal": "",
            "target_users": [],
            "functional_requirements": [],
            "non_functional_requirements": [],
            "acceptance_criteria": [],
            "constraints": [],
            "non_goals": [],
            "assumptions": [],
            "status": "draft",
        },
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Analysis on requirement
# ---------------------------------------------------------------------------


def test_create_analysis_on_requirement_returns_201_and_links():
    project = _create_project()
    req = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()
    response = client.post(f"/requirements/{req['id']}/requirement-analyses")
    assert response.status_code == 201
    data = response.json()
    assert "agent_run" in data
    assert "requirement_analysis" in data
    assert "artifact" in data

    ra = data["requirement_analysis"]
    assert ra["requirement_id"] == req["id"]
    assert ra["ticket_id"] is None
    assert ra["readiness"] in ("ready_for_planning", "needs_clarification")

    run = data["agent_run"]
    assert run["agent_type"] == "requirement_analysis"
    assert run["provider"] == "mock"
    assert run["requirement_id"] == req["id"]
    assert run["ticket_id"] is None

    artifact = data["artifact"]
    assert artifact["artifact_type"] == "requirement_analysis"
    assert artifact["requirement_id"] == req["id"]
    assert artifact["ticket_id"] is None


def test_requirement_status_becomes_analyzed_after_analysis():
    project = _create_project()
    req = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()
    assert req["status"] == "draft"
    resp = client.post(f"/requirements/{req['id']}/requirement-analyses")
    assert resp.status_code == 201
    after = client.get(f"/requirements/{req['id']}").json()
    assert after["status"] == "analyzed"


def test_create_analysis_missing_requirement_404():
    response = client.post("/requirements/nope/requirement-analyses")
    assert response.status_code == 404


def test_create_analysis_unknown_provider_400():
    project = _create_project()
    req = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()
    response = client.post(
        f"/requirements/{req['id']}/requirement-analyses",
        json={"provider": "gemini"},
    )
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


def test_create_analysis_explicit_mock_provider():
    project = _create_project()
    req = client.post(f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD).json()
    response = client.post(
        f"/requirements/{req['id']}/requirement-analyses",
        json={"provider": "mock"},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"
