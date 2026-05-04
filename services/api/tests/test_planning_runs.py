import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.llm.mock import MockLLMProvider
from app.models import Ticket
from app.planning_agent import run_planning_agent
from app.repositories import InMemoryAgentRunRepository, InMemoryArtifactRepository
from datetime import datetime, timezone

client = TestClient(app)

TICKET_PAYLOAD = {"title": "Fix login", "description": "Login fails on mobile"}


def _create_ticket():
    return client.post("/tickets", json=TICKET_PAYLOAD).json()


def test_planning_run_returns_201():
    ticket = _create_ticket()
    response = client.post(f"/tickets/{ticket['id']}/planning-runs")
    assert response.status_code == 201


def test_planning_run_agent_run_shape():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/planning-runs").json()
    run = data["agent_run"]
    assert run["agent_type"] == "planning"
    assert run["provider"] == "mock"
    assert run["model"] == "mock-planning-model"
    assert run["status"] == "completed"
    assert run["error_message"] is None
    assert "id" in run
    assert "started_at" in run
    assert "completed_at" in run


def test_planning_run_artifact_shape():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/planning-runs").json()
    artifact = data["artifact"]
    assert artifact["artifact_type"] == "implementation_brief"
    assert artifact["ticket_id"] == ticket["id"]
    assert artifact["agent_run_id"] == data["agent_run"]["id"]
    assert "id" in artifact
    assert "created_at" in artifact


def test_planning_run_brief_content():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/planning-runs").json()
    assert "# Implementation Brief" in data["artifact"]["content"]


def test_planning_run_updates_ticket_status():
    ticket = _create_ticket()
    client.post(f"/tickets/{ticket['id']}/planning-runs")
    updated = client.get(f"/tickets/{ticket['id']}").json()
    assert updated["status"] == "brief_generated"


def test_get_artifacts_returns_list():
    ticket = _create_ticket()
    client.post(f"/tickets/{ticket['id']}/planning-runs")
    response = client.get(f"/tickets/{ticket['id']}/artifacts")
    assert response.status_code == 200
    artifacts = response.json()
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "implementation_brief"


def test_planning_run_unknown_ticket_404():
    response = client.post("/tickets/nonexistent-id/planning-runs")
    assert response.status_code == 404


def test_get_artifacts_unknown_ticket_404():
    response = client.get("/tickets/nonexistent-id/artifacts")
    assert response.status_code == 404


def test_run_planning_agent_returns_run_and_artifact():
    ticket = Ticket(
        id="test-ticket-id",
        title="Fix login",
        description="Login fails on mobile",
        status="created",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    provider = MockLLMProvider()
    run_repo = InMemoryAgentRunRepository()
    art_repo = InMemoryArtifactRepository()

    run, artifact = run_planning_agent(ticket, provider, run_repo, art_repo)

    assert run.provider == "mock"
    assert run.model == "mock-planning-model"
    assert run.status == "completed"
    assert run.error_message is None
    assert artifact.artifact_type == "implementation_brief"
    assert "# Implementation Brief" in artifact.content
    assert run_repo.get(run.id) is not None
    assert art_repo.list_by_ticket(ticket.id) == [artifact]
