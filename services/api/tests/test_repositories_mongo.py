"""Unit tests for the MongoDB repository provider (Task 40A).

Uses ``mongomock`` so the suite never opens a real Mongo connection.
"""

from __future__ import annotations

from datetime import datetime, timezone

import mongomock
import pytest

from app import config, repositories
from app import repositories_mongo as mongo
from app.models import (
    Approval,
    Artifact,
    CheckRun,
    CommandRun,
    DevTask,
    MemoryLearningRun,
    Project,
    ProjectContext,
    ProjectMemoryCandidate,
    PullRequestDraft,
    Requirement,
    ReviewFeedback,
    Ticket,
    Workspace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["forgeloop_test"]


def _now() -> datetime:
    return datetime(2026, 5, 12, 2, 12, 0, tzinfo=timezone.utc)


def _project(project_id: str = "p1", name: str = "P1") -> Project:
    return Project(
        id=project_id,
        name=name,
        description="d",
        created_at=_now(),
        updated_at=_now(),
    )


def _ticket(ticket_id: str, project_id: str | None = "p1") -> Ticket:
    return Ticket(
        id=ticket_id,
        title="t",
        description="d",
        status="created",
        created_at=_now(),
        updated_at=_now(),
        project_id=project_id,
    )


def _requirement(req_id: str, project_id: str = "p1") -> Requirement:
    return Requirement(
        id=req_id,
        project_id=project_id,
        title="r",
        created_at=_now(),
        updated_at=_now(),
    )


def _dev_task(task_id: str, project_id: str = "p1") -> DevTask:
    return DevTask(
        id=task_id,
        project_id=project_id,
        agent_run_id="agent-1",
        title="task",
        description="d",
        created_at=_now(),
        updated_at=_now(),
    )


def _workspace(ws_id: str, project_id: str = "p1") -> Workspace:
    return Workspace(
        id=ws_id,
        project_id=project_id,
        name="ws",
        root_path="/tmp/ws",
        workspace_type="local_created",
        status="ready",
        created_at=_now(),
        updated_at=_now(),
    )


def _check_run(run_id: str, project_id: str = "p1", target_id: str = "tgt") -> CheckRun:
    return CheckRun(
        id=run_id,
        project_id=project_id,
        target_type="dev_task",
        target_id=target_id,
        status="completed",
        started_at=_now(),
        completed_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )


def _command_run(
    run_id: str,
    project_id: str = "p1",
    workspace_id: str = "w1",
    target_type: str = "manual",
    target_id: str | None = None,
) -> CommandRun:
    return CommandRun(
        id=run_id,
        project_id=project_id,
        workspace_id=workspace_id,
        target_type=target_type,
        target_id=target_id,
        command="pytest",
        status="completed",
        created_at=_now(),
        updated_at=_now(),
    )


def _pr_draft(draft_id: str, project_id: str = "p1") -> PullRequestDraft:
    return PullRequestDraft(
        id=draft_id,
        project_id=project_id,
        code_repository_id="repo-1",
        title="PR",
        body="body",
        source_branch="forgeloop/x",
        created_by="alice",
        created_at=_now(),
        updated_at=_now(),
    )


def _review_feedback(feedback_id: str, project_id: str = "p1") -> ReviewFeedback:
    return ReviewFeedback(
        id=feedback_id,
        project_id=project_id,
        pr_draft_id="pr-1",
        source="manual",
        severity="warning",
        category="other",
        summary="needs work",
        created_at=_now(),
        updated_at=_now(),
    )


def _learning_run(run_id: str, project_id: str = "p1") -> MemoryLearningRun:
    return MemoryLearningRun(
        id=run_id,
        project_id=project_id,
        source_type="manual",
        source_id="src",
        provider="mock",
        model="mock",
        status="completed",
        created_at=_now(),
        updated_at=_now(),
    )


def _candidate(candidate_id: str, project_id: str = "p1") -> ProjectMemoryCandidate:
    return ProjectMemoryCandidate(
        id=candidate_id,
        project_id=project_id,
        memory_type="project_rule",
        source_type="manual",
        title="t",
        content="c",
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_safe_collection_name_accepts_known_names():
    for name in ["tickets", "dev_tasks", "pull_request_drafts", "review_feedback"]:
        assert mongo.safe_collection_name(name) == name


def test_safe_collection_name_rejects_invalid():
    with pytest.raises(ValueError):
        mongo.safe_collection_name("bad name")
    with pytest.raises(ValueError):
        mongo.safe_collection_name("Tickets")
    with pytest.raises(ValueError):
        mongo.safe_collection_name("")


def test_redact_mongo_uri_strips_credentials():
    assert mongo._redact_mongo_uri("mongodb://localhost:27017") == "mongodb://localhost:27017"
    assert mongo._redact_mongo_uri(
        "mongodb://user:secret@host:27017/db"
    ) == "mongodb://host:27017/db"


def test_to_and_from_mongo_document_roundtrip():
    project = _project()
    doc = mongo.to_mongo_document(project)
    assert doc["_id"] == project.id
    assert doc["id"] == project.id
    restored = mongo.from_mongo_document(doc, Project)
    assert restored == project


# ---------------------------------------------------------------------------
# Save / get roundtrips for representative models
# ---------------------------------------------------------------------------


def test_project_roundtrip(db):
    repo = mongo.MongoProjectRepository(db)
    project = _project()
    repo.save(project)
    loaded = repo.get(project.id)
    assert loaded == project
    assert isinstance(loaded.created_at, datetime)


def test_artifact_roundtrip(db):
    repo = mongo.MongoArtifactRepository(db)
    art = Artifact(
        id="a1",
        ticket_id="t1",
        artifact_type="implementation_brief",
        content="hello",
        created_at=_now(),
    )
    repo.save(art)
    assert repo.get("a1") == art
    assert repo.list_by_ticket("t1") == [art]


def test_workspace_roundtrip(db):
    repo = mongo.MongoWorkspaceRepository(db)
    ws = _workspace("w1")
    repo.save(ws)
    assert repo.get("w1") == ws


def test_command_run_roundtrip(db):
    repo = mongo.MongoCommandRunRepository(db)
    run = _command_run("cr1", target_id="tgt-1", target_type="manual")
    repo.save(run)
    assert repo.get("cr1") == run


def test_check_run_roundtrip(db):
    repo = mongo.MongoCheckRunRepository(db)
    run = _check_run("cr1")
    repo.save(run)
    assert repo.get("cr1") == run


def test_pull_request_draft_roundtrip(db):
    repo = mongo.MongoPullRequestDraftRepository(db)
    draft = _pr_draft("pr1")
    repo.save(draft)
    assert repo.get("pr1") == draft


def test_review_feedback_roundtrip(db):
    repo = mongo.MongoReviewFeedbackRepository(db)
    fb = _review_feedback("f1")
    repo.save(fb)
    assert repo.get("f1") == fb


def test_memory_learning_run_roundtrip(db):
    repo = mongo.MongoMemoryLearningRunRepository(db)
    run = _learning_run("ml1")
    repo.save(run)
    assert repo.get("ml1") == run


def test_project_memory_candidate_roundtrip(db):
    repo = mongo.MongoProjectMemoryCandidateRepository(db)
    cand = _candidate("c1")
    repo.save(cand)
    assert repo.get("c1") == cand


def test_project_context_uses_project_id_as_key(db):
    repo = mongo.MongoProjectContextRepository(db)
    ctx = ProjectContext(project_id="p1", architecture_notes="notes")
    repo.save(ctx)
    loaded = repo.get("p1")
    assert loaded == ctx


def test_get_returns_none_when_missing(db):
    repo = mongo.MongoProjectRepository(db)
    assert repo.get("missing") is None


def test_id_is_not_leaked_via_underscore_id(db):
    repo = mongo.MongoProjectRepository(db)
    project = _project()
    repo.save(project)
    loaded = repo.get(project.id)
    assert "_id" not in loaded.model_dump()


# ---------------------------------------------------------------------------
# list_by_* behaviour
# ---------------------------------------------------------------------------


def test_list_by_project_filters_correctly(db):
    repo = mongo.MongoTicketRepository(db)
    repo.save(_ticket("t1", project_id="p1"))
    repo.save(_ticket("t2", project_id="p1"))
    repo.save(_ticket("t3", project_id="p2"))
    p1_ids = sorted(t.id for t in repo.list_by_project("p1"))
    assert p1_ids == ["t1", "t2"]
    assert [t.id for t in repo.list_by_project("p2")] == ["t3"]


def test_list_by_project_for_requirements_and_dev_tasks(db):
    req_repo = mongo.MongoRequirementRepository(db)
    task_repo = mongo.MongoDevTaskRepository(db)
    req_repo.save(_requirement("r1", project_id="p1"))
    req_repo.save(_requirement("r2", project_id="p2"))
    task_repo.save(_dev_task("dt1", project_id="p1"))
    task_repo.save(_dev_task("dt2", project_id="p2"))
    assert [r.id for r in req_repo.list_by_project("p1")] == ["r1"]
    assert [t.id for t in task_repo.list_by_project("p2")] == ["dt2"]


def test_command_run_list_by_workspace(db):
    repo = mongo.MongoCommandRunRepository(db)
    repo.save(_command_run("c1", workspace_id="w1"))
    repo.save(_command_run("c2", workspace_id="w1"))
    repo.save(_command_run("c3", workspace_id="w2"))
    ids = sorted(r.id for r in repo.list_by_workspace("w1"))
    assert ids == ["c1", "c2"]


def test_check_run_list_by_target(db):
    repo = mongo.MongoCheckRunRepository(db)
    repo.save(_check_run("c1", target_id="tgt-1"))
    repo.save(_check_run("c2", target_id="tgt-1"))
    repo.save(_check_run("c3", target_id="tgt-2"))
    ids = sorted(r.id for r in repo.list_by_target("dev_task", "tgt-1"))
    assert ids == ["c1", "c2"]


def test_approval_find_approved_for_target(db):
    repo = mongo.MongoApprovalRepository(db)
    repo.save(
        Approval(
            id="a1",
            project_id="p1",
            target_type="dev_task",
            target_id="dt-1",
            status="pending",
            requested_by="bob",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    repo.save(
        Approval(
            id="a2",
            project_id="p1",
            target_type="dev_task",
            target_id="dt-1",
            status="approved",
            requested_by="bob",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    found = repo.find_approved_for_target("dev_task", "dt-1")
    assert found is not None and found.id == "a2"
    assert repo.find_approved_for_target("dev_task", "missing") is None


# ---------------------------------------------------------------------------
# Provider selection wiring
# ---------------------------------------------------------------------------


def test_local_document_provider_builds_mongo_repositories(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")

    fake_client_factory = lambda *args, **kwargs: mongomock.MongoClient()
    import pymongo as _pymongo

    monkeypatch.setattr(_pymongo, "MongoClient", fake_client_factory)

    repos = repositories.get_repositories()
    assert isinstance(repos.project, mongo.MongoProjectRepository)
    assert isinstance(repos.review_feedback, mongo.MongoReviewFeedbackRepository)
    assert isinstance(repos.command_run, mongo.MongoCommandRunRepository)


def test_local_document_provider_rejects_unsupported_db(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "sqlite")
    with pytest.raises(ValueError):
        repositories.get_repositories()


def test_unreachable_mongo_raises_clear_error(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")
    monkeypatch.setattr(config, "MONGODB_URI", "mongodb://user:secret@unreachable:27017")

    import pymongo as _pymongo
    from pymongo.errors import ServerSelectionTimeoutError

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            self.admin = self

        def command(self, *args, **kwargs):
            raise ServerSelectionTimeoutError("no servers available")

    monkeypatch.setattr(_pymongo, "MongoClient", _BoomClient)

    with pytest.raises(RuntimeError) as excinfo:
        repositories.get_repositories()
    msg = str(excinfo.value)
    assert "MongoDB unreachable" in msg
    assert "secret" not in msg
    assert "unreachable" in msg


def test_memory_provider_does_not_invoke_mongo_factory(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    calls: list[int] = []

    def _boom():
        calls.append(1)
        raise AssertionError("build_mongo_repositories must not run for memory provider")

    monkeypatch.setattr(mongo, "build_mongo_repositories", _boom)
    repos_obj = repositories.get_repositories()
    assert calls == []
    # Sanity: memory-backed repo type
    from app.repositories import InMemoryProjectRepository

    assert isinstance(repos_obj.project, InMemoryProjectRepository)


# ---------------------------------------------------------------------------
# Startup config validation
# ---------------------------------------------------------------------------


def test_validate_startup_config_passes_for_memory(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "memory")
    # Secure posture (post-#45/H1): auth on with a valid-length secret.
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "x" * 40)
    config.validate_startup_config()


def test_validate_startup_config_requires_mongo_uri(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")
    monkeypatch.setattr(config, "MONGODB_URI", "")
    monkeypatch.setattr(config, "AUTH_ENABLED", True)
    monkeypatch.setattr(config, "AUTH_TOKEN_SECRET", "x" * 40)
    with pytest.raises(RuntimeError, match="MONGODB_URI"):
        config.validate_startup_config()


def test_validate_startup_config_rejects_unsupported_local_db(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "sqlite")
    monkeypatch.setattr(config, "AUTH_ENABLED", False)
    with pytest.raises(RuntimeError):
        config.validate_startup_config()


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


def test_ensure_indexes_creates_expected_indexes(db):
    mongo._ensure_indexes(db)
    project_indexes = list(db["tickets"].list_indexes())
    keys = {tuple(idx["key"].items()) for idx in project_indexes}
    assert (("project_id", 1),) in keys

    approval_indexes = list(db["approvals"].list_indexes())
    approval_keys = {tuple(idx["key"].items()) for idx in approval_indexes}
    assert (("target_type", 1), ("target_id", 1), ("status", 1)) in approval_keys
