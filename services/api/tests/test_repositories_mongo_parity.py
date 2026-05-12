"""Release 8 Task 42 — parity/index/serialization tests for the local_document
(MongoDB) provider. Uses ``mongomock`` only; no real Mongo connection.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import mongomock
import pytest

from app import config, repositories
from app import repositories_mongo as mongo
from app.models import (
    AuditEvent,
    Project,
)


def _now() -> datetime:
    return datetime(2026, 5, 12, 3, 11, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["forgeloop_parity_test"]


@pytest.fixture
def mongo_repos(monkeypatch):
    """Build the full Mongo Repositories container using mongomock as MongoClient."""
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")

    import pymongo as _pymongo

    def _fake_client(*args, **kwargs):
        return mongomock.MongoClient(tz_aware=True)

    monkeypatch.setattr(_pymongo, "MongoClient", _fake_client)
    return repositories.get_repositories()


# ---------------------------------------------------------------------------
# Parity: every dataclass field is implemented
# ---------------------------------------------------------------------------


def test_every_repository_field_is_mongo_backed(mongo_repos):
    """Each field on the Repositories container must be a Mongo* repo instance."""
    for f in dataclasses.fields(mongo_repos):
        repo = getattr(mongo_repos, f.name)
        cls_name = type(repo).__name__
        assert cls_name.startswith("Mongo"), (
            f"Repository {f.name} resolved to {cls_name}, expected Mongo*"
        )


def test_local_document_repos_expose_expected_repo_fields(mongo_repos):
    """Sanity-check the high-value repos by name."""
    for name in [
        "project",
        "ticket",
        "artifact",
        "requirement",
        "dev_task",
        "subtask",
        "approval",
        "audit_event",
        "code_repository",
        "repo_safety_profile",
        "epic",
        "check_definition",
        "check_run",
        "tool_runner_definition",
        "tool_run",
        "pr_draft",
        "pr_review",
        "ci_event",
        "ci_analysis",
        "incident",
        "incident_analysis",
        "memory_learning_run",
        "memory_candidate",
        "workspace",
        "command_definition",
        "command_run",
        "workspace_branch",
        "git_commit_record",
        "review_feedback",
        "revision_work_item",
    ]:
        assert hasattr(mongo_repos, name), f"Missing repository field: {name}"


# ---------------------------------------------------------------------------
# Index plan covers expected fields
# ---------------------------------------------------------------------------


def test_index_plan_contains_common_lookup_fields():
    plan = mongo._INDEX_PLAN
    assert "project_id" in plan["tickets"]
    assert "workspace_id" in plan["command_runs"]
    assert "pr_draft_id" in plan["review_feedback"]
    assert "dev_task_id" in plan["pull_request_drafts"]
    assert "code_repository_id" in plan["workspaces"]
    # source_type+source_id composite index for memory candidates
    assert any(
        isinstance(s, list) and any("source_type" in t for t in s)
        for s in plan["project_memory_candidates"]
    )
    # status indexes added by Task 42
    assert "status" in plan["dev_tasks"]
    assert "status" in plan["check_runs"]
    assert "status" in plan["incidents"]


def test_ensure_indexes_is_idempotent(db):
    mongo._ensure_indexes(db)
    mongo._ensure_indexes(db)
    info = db["tickets"].index_information()
    assert any("project_id" in name for name in info.keys())


def test_collection_names_are_snake_case():
    for name in mongo._INDEX_PLAN.keys():
        assert mongo.safe_collection_name(name) == name


# ---------------------------------------------------------------------------
# Serialization hardening
# ---------------------------------------------------------------------------


def test_datetime_round_trip_preserves_tz(db):
    repo = mongo.MongoProjectRepository(db)
    project = Project(
        id="p_tz",
        name="P",
        description="d",
        created_at=_now(),
        updated_at=_now(),
    )
    repo.save(project)
    loaded = repo.get("p_tz")
    assert loaded.created_at.tzinfo is not None
    assert loaded.created_at == project.created_at


def test_nested_dict_payload_round_trips(db):
    repo = mongo.MongoAuditEventRepository(db)
    ev = AuditEvent(
        id="ae_nested",
        project_id="p1",
        actor_type="user",
        actor_id="u1",
        action="approval_approved",
        target_type="approval",
        target_id="a1",
        details={"nested": {"k": [1, 2, 3]}, "list": ["a", "b"]},
        created_at=_now(),
    )
    repo.save(ev)
    loaded = repo.get("ae_nested")
    assert loaded.details == {"nested": {"k": [1, 2, 3]}, "list": ["a", "b"]}


def test_id_not_leaked_in_audit_event(db):
    repo = mongo.MongoAuditEventRepository(db)
    ev = AuditEvent(
        id="ae_id_leak",
        project_id="p1",
        actor_type="user",
        actor_id="u1",
        action="approval_approved",
        target_type="approval",
        target_id="a1",
        details={},
        created_at=_now(),
    )
    repo.save(ev)
    loaded = repo.get("ae_id_leak")
    assert "_id" not in loaded.model_dump()


# ---------------------------------------------------------------------------
# Provider isolation
# ---------------------------------------------------------------------------


def test_local_document_mode_does_not_initialize_firestore(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "local_document")
    monkeypatch.setattr(config, "LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")

    import pymongo as _pymongo

    monkeypatch.setattr(_pymongo, "MongoClient", lambda *a, **k: mongomock.MongoClient())

    class _BoomFirestore:
        def __getattr__(self, item):
            raise AssertionError("Firestore must not be initialized in local_document mode")

    import sys

    monkeypatch.setitem(sys.modules, "google.cloud.firestore", _BoomFirestore())
    repositories.get_repositories()  # should succeed without touching firestore


def test_firestore_mode_does_not_initialize_mongo(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "firestore")

    def _boom_build():
        raise AssertionError("Mongo factory must not run in firestore mode")

    monkeypatch.setattr(mongo, "build_mongo_repositories", _boom_build)

    class _FakeClient:
        def collection(self, _name):
            class _Coll:
                def document(self, _id):
                    class _Doc:
                        def get(self):
                            class _Snap:
                                exists = False

                                def to_dict(self):
                                    return {}

                            return _Snap()

                        def set(self, *a, **k):
                            pass

                    return _Doc()

                def where(self, *a, **k):
                    class _Q:
                        def stream(self):
                            return iter([])

                        def where(self, *a, **k):
                            return self

                    return _Q()

            return _Coll()

    class _FsModule:
        Client = lambda *a, **k: _FakeClient()

    import sys

    monkeypatch.setitem(sys.modules, "google.cloud", type("M", (), {"firestore": _FsModule})())
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", _FsModule)
    repositories.get_repositories()


def test_unknown_repository_provider_rejected(monkeypatch):
    monkeypatch.setattr(config, "REPOSITORY_PROVIDER", "weird")
    with pytest.raises(ValueError):
        repositories.get_repositories()
