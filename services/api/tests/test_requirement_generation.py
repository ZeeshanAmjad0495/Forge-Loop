from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import config
from app.llm.mock import MockLLMProvider
from app.main import app
from app.models import Project
from app.repositories import (
    InMemoryAgentRunRepository,
    InMemoryArtifactRepository,
    InMemoryRequirementRepository,
)
from app.requirement_generation_agent import run_requirement_generation_agent

client = TestClient(app)


PROJECT_PAYLOAD = {"name": "Insurance CSV", "description": "Validate CSV uploads."}


def _create_project() -> dict:
    return client.post("/projects", json=PROJECT_PAYLOAD).json()


# ---------------------------------------------------------------------------
# POST endpoint
# ---------------------------------------------------------------------------


def test_create_requirement_generation_returns_201():
    project = _create_project()
    response = client.post(f"/projects/{project['id']}/requirement-generations")
    assert response.status_code == 201


def test_response_includes_agent_run():
    project = _create_project()
    data = client.post(f"/projects/{project['id']}/requirement-generations").json()
    assert "agent_run" in data
    run = data["agent_run"]
    assert run["agent_type"] == "requirement_generation"
    assert run["provider"] == "mock"
    assert run["status"] == "completed"
    assert run["error_message"] is None


def test_response_includes_generated_requirements():
    project = _create_project()
    data = client.post(f"/projects/{project['id']}/requirement-generations").json()
    requirements = data["requirements"]
    assert isinstance(requirements, list)
    assert len(requirements) >= 2
    for r in requirements:
        assert r["source"] == "agent_generated"
        assert r["status"] == "draft"
        assert r["project_id"] == project["id"]
        assert isinstance(r["functional_requirements"], list)
        assert isinstance(r["acceptance_criteria"], list)


def test_generated_requirements_persisted():
    project = _create_project()
    gen = client.post(f"/projects/{project['id']}/requirement-generations").json()
    listing = client.get(f"/projects/{project['id']}/requirements").json()
    listed_ids = {r["id"] for r in listing}
    for r in gen["requirements"]:
        assert r["id"] in listed_ids


def test_artifact_created_with_requirement_generation_type():
    project = _create_project()
    data = client.post(f"/projects/{project['id']}/requirement-generations").json()
    artifact = data["artifact"]
    assert artifact["artifact_type"] == "requirement_generation"
    assert artifact["agent_run_id"] == data["agent_run"]["id"]


def test_missing_project_returns_404():
    response = client.post("/projects/nonexistent-project/requirement-generations")
    assert response.status_code == 404


def test_unknown_provider_returns_400():
    project = _create_project()
    response = client.post(
        f"/projects/{project['id']}/requirement-generations",
        json={"provider": "gemini"},
    )
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


def test_unconfigured_provider_returns_400(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    project = _create_project()
    response = client.post(
        f"/projects/{project['id']}/requirement-generations",
        json={"provider": "deepseek"},
    )
    assert response.status_code == 400
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_explicit_mock_provider():
    project = _create_project()
    response = client.post(
        f"/projects/{project['id']}/requirement-generations",
        json={"provider": "mock"},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"


def test_null_provider_uses_default():
    project = _create_project()
    response = client.post(
        f"/projects/{project['id']}/requirement-generations",
        json={"provider": None},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"


def test_audit_events_emitted():
    project = _create_project()
    gen = client.post(f"/projects/{project['id']}/requirement-generations").json()
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "requirement_generation_created" in actions
    requirement_created_count = sum(1 for a in actions if a == "requirement_created")
    assert requirement_created_count == len(gen["requirements"])


def test_manual_requirement_creation_still_works():
    project = _create_project()
    payload = {"title": "Manual req", "problem_statement": "p"}
    response = client.post(f"/projects/{project['id']}/requirements", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "manual"
    assert body["status"] == "draft"


# ---------------------------------------------------------------------------
# Unit tests for agent function
# ---------------------------------------------------------------------------


def _project(project_id: str = "p-unit", name: str = "Unit project") -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=project_id,
        name=name,
        description="A project used in unit tests.",
        repo_url=None,
        tech_stack=["python", "fastapi"],
        status="active",
        created_at=now,
        updated_at=now,
    )


def test_run_requirement_generation_agent_returns_tuple_and_persists():
    project = _project()
    provider = MockLLMProvider()
    run_repo = InMemoryAgentRunRepository()
    art_repo = InMemoryArtifactRepository()
    req_repo = InMemoryRequirementRepository()

    run, requirements, artifact = run_requirement_generation_agent(
        project, provider, run_repo, art_repo, req_repo
    )

    assert run.agent_type == "requirement_generation"
    assert run.provider == "mock"
    assert run.status == "completed"
    assert run.error_message is None

    assert len(requirements) >= 2
    for r in requirements:
        assert r.project_id == project.id
        assert r.source == "agent_generated"
        assert r.status == "draft"

    assert artifact.artifact_type == "requirement_generation"
    assert artifact.agent_run_id == run.id

    assert run_repo.get(run.id) is not None
    persisted = req_repo.list_by_project(project.id)
    assert {r.id for r in persisted} == {r.id for r in requirements}
