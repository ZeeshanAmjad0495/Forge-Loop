from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import config
from app.llm.mock import MockLLMProvider
from app.main import app
from app.models import Ticket
from app.repositories import (
    InMemoryAgentRunRepository,
    InMemoryArtifactRepository,
    InMemoryRequirementAnalysisRepository,
)
from app.requirement_analysis_agent import run_requirement_analysis_agent

client = TestClient(app)

TICKET_PAYLOAD = {"title": "Add CSV export", "description": "Users need to export their data as CSV."}


def _create_ticket() -> dict:
    return client.post("/tickets", json=TICKET_PAYLOAD).json()


# ---------------------------------------------------------------------------
# POST endpoint
# ---------------------------------------------------------------------------


def test_create_analysis_returns_201():
    ticket = _create_ticket()
    response = client.post(f"/tickets/{ticket['id']}/requirement-analyses")
    assert response.status_code == 201


def test_create_analysis_shape():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/requirement-analyses").json()
    assert "agent_run" in data
    assert "requirement_analysis" in data
    assert "artifact" in data


def test_create_analysis_agent_run_fields():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/requirement-analyses").json()
    run = data["agent_run"]
    assert run["agent_type"] == "requirement_analysis"
    assert run["provider"] == "mock"
    assert run["status"] == "completed"
    assert run["error_message"] is None
    assert "id" in run
    assert "started_at" in run
    assert "completed_at" in run


def test_create_analysis_readiness_valid():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/requirement-analyses").json()
    ra = data["requirement_analysis"]
    assert ra["readiness"] in ("ready_for_planning", "needs_clarification")


def test_create_analysis_artifact_type():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/requirement-analyses").json()
    assert data["artifact"]["artifact_type"] == "requirement_analysis"
    assert data["artifact"]["ticket_id"] == ticket["id"]


def test_create_analysis_analysis_fields():
    ticket = _create_ticket()
    data = client.post(f"/tickets/{ticket['id']}/requirement-analyses").json()
    ra = data["requirement_analysis"]
    assert "summary" in ra
    assert "clarified_requirement" in ra
    assert isinstance(ra["assumptions"], list)
    assert isinstance(ra["ambiguities"], list)
    assert isinstance(ra["clarification_questions"], list)
    assert isinstance(ra["risks"], list)
    assert isinstance(ra["affected_areas"], list)


def test_create_analysis_missing_ticket_404():
    response = client.post("/tickets/nonexistent-ticket/requirement-analyses")
    assert response.status_code == 404


def test_create_analysis_unknown_provider_400():
    ticket = _create_ticket()
    response = client.post(
        f"/tickets/{ticket['id']}/requirement-analyses",
        json={"provider": "gemini"},
    )
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]


def test_create_analysis_unconfigured_provider_400(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    ticket = _create_ticket()
    response = client.post(
        f"/tickets/{ticket['id']}/requirement-analyses",
        json={"provider": "deepseek"},
    )
    assert response.status_code == 400
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_create_analysis_explicit_mock_provider():
    ticket = _create_ticket()
    response = client.post(
        f"/tickets/{ticket['id']}/requirement-analyses",
        json={"provider": "mock"},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"


def test_create_analysis_null_provider_uses_default():
    ticket = _create_ticket()
    response = client.post(
        f"/tickets/{ticket['id']}/requirement-analyses",
        json={"provider": None},
    )
    assert response.status_code == 201
    assert response.json()["agent_run"]["provider"] == "mock"


# ---------------------------------------------------------------------------
# GET endpoint
# ---------------------------------------------------------------------------


def test_list_analyses_returns_empty_list():
    ticket = _create_ticket()
    response = client.get(f"/tickets/{ticket['id']}/requirement-analyses")
    assert response.status_code == 200
    assert response.json() == []


def test_list_analyses_returns_created_analysis():
    ticket = _create_ticket()
    client.post(f"/tickets/{ticket['id']}/requirement-analyses")
    response = client.get(f"/tickets/{ticket['id']}/requirement-analyses")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["ticket_id"] == ticket["id"]
    assert items[0]["readiness"] in ("ready_for_planning", "needs_clarification")


def test_list_analyses_missing_ticket_404():
    response = client.get("/tickets/nonexistent-ticket/requirement-analyses")
    assert response.status_code == 404


def test_list_analyses_multiple():
    ticket = _create_ticket()
    client.post(f"/tickets/{ticket['id']}/requirement-analyses")
    client.post(f"/tickets/{ticket['id']}/requirement-analyses")
    response = client.get(f"/tickets/{ticket['id']}/requirement-analyses")
    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# Unit tests for agent function
# ---------------------------------------------------------------------------


def test_run_requirement_analysis_agent_returns_tuple():
    ticket = Ticket(
        id="t-unit",
        title="Add CSV export",
        description="Users need to export data as CSV.",
        status="created",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    provider = MockLLMProvider()
    run_repo = InMemoryAgentRunRepository()
    art_repo = InMemoryArtifactRepository()
    ana_repo = InMemoryRequirementAnalysisRepository()

    run, analysis, artifact = run_requirement_analysis_agent(ticket, provider, run_repo, art_repo, ana_repo)

    assert run.agent_type == "requirement_analysis"
    assert run.provider == "mock"
    assert run.status == "completed"
    assert run.error_message is None

    assert analysis.ticket_id == ticket.id
    assert analysis.agent_run_id == run.id
    assert analysis.readiness in ("ready_for_planning", "needs_clarification")
    assert isinstance(analysis.assumptions, list)
    assert isinstance(analysis.clarification_questions, list)

    assert artifact.artifact_type == "requirement_analysis"
    assert artifact.ticket_id == ticket.id
    assert artifact.agent_run_id == run.id


def test_run_requirement_analysis_agent_persists_all():
    ticket = Ticket(
        id="t-persist",
        title="Fix login",
        description="Login fails on mobile.",
        status="created",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    provider = MockLLMProvider()
    run_repo = InMemoryAgentRunRepository()
    art_repo = InMemoryArtifactRepository()
    ana_repo = InMemoryRequirementAnalysisRepository()

    run, analysis, artifact = run_requirement_analysis_agent(ticket, provider, run_repo, art_repo, ana_repo)

    assert run_repo.get(run.id) is not None
    assert ana_repo.list_by_ticket(ticket.id) == [analysis]
    assert art_repo.list_by_ticket(ticket.id) == [artifact]
