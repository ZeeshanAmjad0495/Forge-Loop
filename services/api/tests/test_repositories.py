from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app import config
from app.models import Artifact, Ticket
from app.repositories import (
    FirestoreAgentRunRepository,
    FirestoreApprovalRepository,
    FirestoreArtifactRepository,
    FirestoreAuditEventRepository,
    FirestoreCodeRepositoryRepository,
    FirestoreDevTaskRepository,
    FirestoreProjectContextRepository,
    FirestoreProjectRepository,
    FirestoreRequirementAnalysisRepository,
    FirestoreRequirementRepository,
    FirestoreRepoSafetyProfileRepository,
    FirestoreSubtaskRepository,
    FirestoreTicketRepository,
    InMemoryAgentRunRepository,
    InMemoryApprovalRepository,
    InMemoryArtifactRepository,
    InMemoryAuditEventRepository,
    InMemoryCodeRepositoryRepository,
    InMemoryDevTaskRepository,
    InMemoryProjectContextRepository,
    InMemoryProjectRepository,
    InMemoryRequirementAnalysisRepository,
    InMemoryRequirementRepository,
    InMemoryRepoSafetyProfileRepository,
    InMemorySubtaskRepository,
    InMemoryTicketRepository,
    get_repositories,
)


def test_default_repository_is_memory():
    tickets, runs, artifacts, projects, contexts, analyses, requirements, dev_tasks, subtasks, approvals, audit_events, code_repos, safety_profiles = get_repositories()
    assert isinstance(tickets, InMemoryTicketRepository)
    assert isinstance(runs, InMemoryAgentRunRepository)
    assert isinstance(artifacts, InMemoryArtifactRepository)
    assert isinstance(projects, InMemoryProjectRepository)
    assert isinstance(contexts, InMemoryProjectContextRepository)
    assert isinstance(analyses, InMemoryRequirementAnalysisRepository)
    assert isinstance(requirements, InMemoryRequirementRepository)
    assert isinstance(dev_tasks, InMemoryDevTaskRepository)
    assert isinstance(subtasks, InMemorySubtaskRepository)
    assert isinstance(approvals, InMemoryApprovalRepository)
    assert isinstance(audit_events, InMemoryAuditEventRepository)
    assert isinstance(code_repos, InMemoryCodeRepositoryRepository)
    assert isinstance(safety_profiles, InMemoryRepoSafetyProfileRepository)


def test_memory_repository_explicitly(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    tickets, runs, artifacts, projects, contexts, analyses, requirements, dev_tasks, subtasks, approvals, audit_events, code_repos, safety_profiles = get_repositories()
    assert isinstance(tickets, InMemoryTicketRepository)
    assert isinstance(runs, InMemoryAgentRunRepository)
    assert isinstance(artifacts, InMemoryArtifactRepository)
    assert isinstance(projects, InMemoryProjectRepository)
    assert isinstance(contexts, InMemoryProjectContextRepository)
    assert isinstance(analyses, InMemoryRequirementAnalysisRepository)
    assert isinstance(requirements, InMemoryRequirementRepository)
    assert isinstance(dev_tasks, InMemoryDevTaskRepository)
    assert isinstance(subtasks, InMemorySubtaskRepository)
    assert isinstance(approvals, InMemoryApprovalRepository)
    assert isinstance(audit_events, InMemoryAuditEventRepository)
    assert isinstance(code_repos, InMemoryCodeRepositoryRepository)
    assert isinstance(safety_profiles, InMemoryRepoSafetyProfileRepository)


def test_firestore_repository_selected(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "firestore")
    with patch("google.cloud.firestore.Client"):
        tickets, runs, artifacts, projects, contexts, analyses, requirements, dev_tasks, subtasks, approvals, audit_events, code_repos, safety_profiles = get_repositories()
    assert isinstance(tickets, FirestoreTicketRepository)
    assert isinstance(runs, FirestoreAgentRunRepository)
    assert isinstance(artifacts, FirestoreArtifactRepository)
    assert isinstance(projects, FirestoreProjectRepository)
    assert isinstance(contexts, FirestoreProjectContextRepository)
    assert isinstance(analyses, FirestoreRequirementAnalysisRepository)
    assert isinstance(requirements, FirestoreRequirementRepository)
    assert isinstance(dev_tasks, FirestoreDevTaskRepository)
    assert isinstance(subtasks, FirestoreSubtaskRepository)
    assert isinstance(approvals, FirestoreApprovalRepository)
    assert isinstance(audit_events, FirestoreAuditEventRepository)
    assert isinstance(code_repos, FirestoreCodeRepositoryRepository)
    assert isinstance(safety_profiles, FirestoreRepoSafetyProfileRepository)


def test_unknown_repository_raises(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "postgres")
    with pytest.raises(ValueError, match="Unknown REPOSITORY_PROVIDER"):
        get_repositories()


def test_firestore_ticket_save_and_get():
    now = datetime.now(timezone.utc)
    ticket_data = {
        "id": "t1",
        "title": "Fix login",
        "description": "Login fails on mobile",
        "status": "created",
        "created_at": now,
        "updated_at": now,
    }
    ticket = Ticket(**ticket_data)

    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = ticket_data
    mock_doc.get.return_value = mock_snap
    mock_client.collection.return_value.document.return_value = mock_doc

    repo = FirestoreTicketRepository(mock_client)
    repo.save(ticket)
    mock_doc.set.assert_called_once()
    saved_payload = mock_doc.set.call_args[0][0]
    assert saved_payload["id"] == "t1"
    assert saved_payload["status"] == "created"

    result = repo.get("t1")
    assert result is not None
    assert result.id == "t1"
    assert result.title == "Fix login"


def test_firestore_ticket_get_returns_none_when_missing():
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_snap = MagicMock()
    mock_snap.exists = False
    mock_doc.get.return_value = mock_snap
    mock_client.collection.return_value.document.return_value = mock_doc

    repo = FirestoreTicketRepository(mock_client)
    assert repo.get("missing") is None


def test_firestore_artifact_list_by_ticket():
    now = datetime.now(timezone.utc)
    artifact_data = {
        "id": "a1",
        "ticket_id": "t1",
        "agent_run_id": "r1",
        "artifact_type": "implementation_brief",
        "content": "# Implementation Brief",
        "created_at": now,
    }

    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = artifact_data
    mock_query.stream.return_value = [mock_doc]
    mock_collection = MagicMock()
    mock_collection.where.return_value = mock_query
    mock_client.collection.return_value = mock_collection

    repo = FirestoreArtifactRepository(mock_client)
    result = repo.list_by_ticket("t1")

    mock_collection.where.assert_called_once_with("ticket_id", "==", "t1")
    assert len(result) == 1
    assert isinstance(result[0], Artifact)
    assert result[0].ticket_id == "t1"
