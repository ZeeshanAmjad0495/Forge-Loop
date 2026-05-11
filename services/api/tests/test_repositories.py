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
    FirestoreCheckDefinitionRepository,
    FirestoreCheckRunRepository,
    FirestoreCIAnalysisRepository,
    FirestoreCIEventRepository,
    FirestoreCodeRepositoryRepository,
    FirestoreDevTaskRepository,
    FirestoreEpicRepository,
    FirestoreIncidentAnalysisRepository,
    FirestoreIncidentRepository,
    FirestoreMemoryLearningRunRepository,
    FirestoreProjectContextRepository,
    FirestoreProjectMemoryCandidateRepository,
    FirestoreProjectRepository,
    FirestoreRequirementAnalysisRepository,
    FirestoreRequirementRepository,
    FirestoreRepoSafetyProfileRepository,
    FirestoreSubtaskRepository,
    FirestoreTicketRepository,
    FirestoreToolRunnerDefinitionRepository,
    FirestoreToolRunRepository,
    FirestorePullRequestDraftRepository,
    FirestorePullRequestReviewRepository,
    InMemoryAgentRunRepository,
    InMemoryApprovalRepository,
    InMemoryArtifactRepository,
    InMemoryAuditEventRepository,
    InMemoryCheckDefinitionRepository,
    InMemoryCheckRunRepository,
    InMemoryCIAnalysisRepository,
    InMemoryCIEventRepository,
    InMemoryCodeRepositoryRepository,
    InMemoryDevTaskRepository,
    InMemoryEpicRepository,
    InMemoryIncidentAnalysisRepository,
    InMemoryIncidentRepository,
    InMemoryMemoryLearningRunRepository,
    InMemoryProjectContextRepository,
    InMemoryProjectMemoryCandidateRepository,
    InMemoryProjectRepository,
    InMemoryRequirementAnalysisRepository,
    InMemoryRequirementRepository,
    InMemoryRepoSafetyProfileRepository,
    InMemorySubtaskRepository,
    InMemoryTicketRepository,
    InMemoryToolRunnerDefinitionRepository,
    InMemoryToolRunRepository,
    InMemoryPullRequestDraftRepository,
    InMemoryPullRequestReviewRepository,
    get_repositories,
)


def test_default_repository_is_memory():
    repos = get_repositories()
    assert isinstance(repos.ticket, InMemoryTicketRepository)
    assert isinstance(repos.agent_run, InMemoryAgentRunRepository)
    assert isinstance(repos.artifact, InMemoryArtifactRepository)
    assert isinstance(repos.project, InMemoryProjectRepository)
    assert isinstance(repos.project_context, InMemoryProjectContextRepository)
    assert isinstance(repos.requirement_analysis, InMemoryRequirementAnalysisRepository)
    assert isinstance(repos.requirement, InMemoryRequirementRepository)
    assert isinstance(repos.dev_task, InMemoryDevTaskRepository)
    assert isinstance(repos.subtask, InMemorySubtaskRepository)
    assert isinstance(repos.approval, InMemoryApprovalRepository)
    assert isinstance(repos.audit_event, InMemoryAuditEventRepository)
    assert isinstance(repos.code_repository, InMemoryCodeRepositoryRepository)
    assert isinstance(repos.repo_safety_profile, InMemoryRepoSafetyProfileRepository)
    assert isinstance(repos.epic, InMemoryEpicRepository)
    assert isinstance(repos.check_definition, InMemoryCheckDefinitionRepository)
    assert isinstance(repos.check_run, InMemoryCheckRunRepository)
    assert isinstance(repos.tool_runner_definition, InMemoryToolRunnerDefinitionRepository)
    assert isinstance(repos.tool_run, InMemoryToolRunRepository)
    assert isinstance(repos.pr_draft, InMemoryPullRequestDraftRepository)
    assert isinstance(repos.pr_review, InMemoryPullRequestReviewRepository)
    assert isinstance(repos.ci_event, InMemoryCIEventRepository)
    assert isinstance(repos.ci_analysis, InMemoryCIAnalysisRepository)
    assert isinstance(repos.incident, InMemoryIncidentRepository)
    assert isinstance(repos.incident_analysis, InMemoryIncidentAnalysisRepository)
    assert isinstance(repos.memory_learning_run, InMemoryMemoryLearningRunRepository)
    assert isinstance(repos.memory_candidate, InMemoryProjectMemoryCandidateRepository)


def test_memory_repository_explicitly(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    repos = get_repositories()
    assert isinstance(repos.ticket, InMemoryTicketRepository)
    assert isinstance(repos.agent_run, InMemoryAgentRunRepository)
    assert isinstance(repos.artifact, InMemoryArtifactRepository)
    assert isinstance(repos.project, InMemoryProjectRepository)
    assert isinstance(repos.project_context, InMemoryProjectContextRepository)
    assert isinstance(repos.requirement_analysis, InMemoryRequirementAnalysisRepository)
    assert isinstance(repos.requirement, InMemoryRequirementRepository)
    assert isinstance(repos.dev_task, InMemoryDevTaskRepository)
    assert isinstance(repos.subtask, InMemorySubtaskRepository)
    assert isinstance(repos.approval, InMemoryApprovalRepository)
    assert isinstance(repos.audit_event, InMemoryAuditEventRepository)
    assert isinstance(repos.code_repository, InMemoryCodeRepositoryRepository)
    assert isinstance(repos.repo_safety_profile, InMemoryRepoSafetyProfileRepository)
    assert isinstance(repos.epic, InMemoryEpicRepository)
    assert isinstance(repos.check_definition, InMemoryCheckDefinitionRepository)
    assert isinstance(repos.check_run, InMemoryCheckRunRepository)
    assert isinstance(repos.tool_runner_definition, InMemoryToolRunnerDefinitionRepository)
    assert isinstance(repos.tool_run, InMemoryToolRunRepository)
    assert isinstance(repos.pr_draft, InMemoryPullRequestDraftRepository)
    assert isinstance(repos.pr_review, InMemoryPullRequestReviewRepository)
    assert isinstance(repos.ci_event, InMemoryCIEventRepository)
    assert isinstance(repos.ci_analysis, InMemoryCIAnalysisRepository)
    assert isinstance(repos.incident, InMemoryIncidentRepository)
    assert isinstance(repos.incident_analysis, InMemoryIncidentAnalysisRepository)
    assert isinstance(repos.memory_learning_run, InMemoryMemoryLearningRunRepository)
    assert isinstance(repos.memory_candidate, InMemoryProjectMemoryCandidateRepository)


def test_firestore_repository_selected(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "firestore")
    with patch("google.cloud.firestore.Client"):
        repos = get_repositories()
    assert isinstance(repos.ticket, FirestoreTicketRepository)
    assert isinstance(repos.agent_run, FirestoreAgentRunRepository)
    assert isinstance(repos.artifact, FirestoreArtifactRepository)
    assert isinstance(repos.project, FirestoreProjectRepository)
    assert isinstance(repos.project_context, FirestoreProjectContextRepository)
    assert isinstance(repos.requirement_analysis, FirestoreRequirementAnalysisRepository)
    assert isinstance(repos.requirement, FirestoreRequirementRepository)
    assert isinstance(repos.dev_task, FirestoreDevTaskRepository)
    assert isinstance(repos.subtask, FirestoreSubtaskRepository)
    assert isinstance(repos.approval, FirestoreApprovalRepository)
    assert isinstance(repos.audit_event, FirestoreAuditEventRepository)
    assert isinstance(repos.code_repository, FirestoreCodeRepositoryRepository)
    assert isinstance(repos.repo_safety_profile, FirestoreRepoSafetyProfileRepository)
    assert isinstance(repos.epic, FirestoreEpicRepository)
    assert isinstance(repos.check_definition, FirestoreCheckDefinitionRepository)
    assert isinstance(repos.check_run, FirestoreCheckRunRepository)
    assert isinstance(repos.tool_runner_definition, FirestoreToolRunnerDefinitionRepository)
    assert isinstance(repos.tool_run, FirestoreToolRunRepository)
    assert isinstance(repos.pr_draft, FirestorePullRequestDraftRepository)
    assert isinstance(repos.pr_review, FirestorePullRequestReviewRepository)
    assert isinstance(repos.ci_event, FirestoreCIEventRepository)
    assert isinstance(repos.ci_analysis, FirestoreCIAnalysisRepository)
    assert isinstance(repos.incident, FirestoreIncidentRepository)
    assert isinstance(repos.incident_analysis, FirestoreIncidentAnalysisRepository)
    assert isinstance(repos.memory_learning_run, FirestoreMemoryLearningRunRepository)
    assert isinstance(repos.memory_candidate, FirestoreProjectMemoryCandidateRepository)


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
