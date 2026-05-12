import uuid
from datetime import datetime, timezone

from app.models import ProjectMemoryCandidate
from app.repositories import InMemoryProjectMemoryCandidateRepository
from app.repositories_state import memory_candidate_repo
from app.services.memory_retrieval import (
    DEFAULT_POLICIES,
    MemoryRetrievalRequest,
    retrieve_memory,
)


def _make(
    project_id: str = "p1",
    memory_type: str = "project_rule",
    status: str = "approved",
    tags: list[str] | None = None,
    title: str = "rule",
    content: str = "x",
    source_type: str = "manual",
    source_id: str | None = None,
) -> ProjectMemoryCandidate:
    now = datetime.now(timezone.utc)
    return ProjectMemoryCandidate(
        id=str(uuid.uuid4()),
        project_id=project_id,
        memory_type=memory_type,  # type: ignore[arg-type]
        title=title,
        content=content,
        tags=list(tags or []),
        status=status,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        source_id=source_id,
        created_at=now,
        updated_at=now,
    )


def test_default_policy_for_coding_instruction():
    assert "project_rule" in DEFAULT_POLICIES["coding_instruction"]
    assert "coding_standard" in DEFAULT_POLICIES["coding_instruction"]


def test_retrieve_excludes_non_approved():
    repo = InMemoryProjectMemoryCandidateRepository()
    repo.save(_make(memory_type="project_rule", status="approved"))
    repo.save(_make(memory_type="project_rule", status="proposed"))
    repo.save(_make(memory_type="project_rule", status="rejected"))
    res = retrieve_memory(
        repo, "p1", MemoryRetrievalRequest(purpose="coding_instruction")
    )
    assert len(res.items) == 1


def test_retrieve_filters_by_memory_type_default_policy():
    repo = InMemoryProjectMemoryCandidateRepository()
    repo.save(_make(memory_type="project_rule"))
    repo.save(_make(memory_type="prompt_note"))
    res = retrieve_memory(
        repo, "p1", MemoryRetrievalRequest(purpose="coding_instruction")
    )
    assert len(res.items) == 1
    assert res.items[0].memory_type == "project_rule"


def test_retrieve_filters_by_tags():
    repo = InMemoryProjectMemoryCandidateRepository()
    repo.save(_make(memory_type="project_rule", tags=["api"]))
    repo.save(_make(memory_type="project_rule", tags=["frontend"]))
    res = retrieve_memory(
        repo,
        "p1",
        MemoryRetrievalRequest(purpose="coding_instruction", tags=["api"]),
    )
    assert len(res.items) == 1
    assert "api" in res.items[0].tags


def test_retrieve_respects_max_items():
    repo = InMemoryProjectMemoryCandidateRepository()
    for _ in range(5):
        repo.save(_make(memory_type="project_rule"))
    res = retrieve_memory(
        repo,
        "p1",
        MemoryRetrievalRequest(purpose="coding_instruction", max_items=2),
    )
    assert len(res.items) == 2
    assert res.total_matched == 5


def test_retrieve_explicit_memory_types_overrides_policy():
    repo = InMemoryProjectMemoryCandidateRepository()
    repo.save(_make(memory_type="prompt_note"))
    res = retrieve_memory(
        repo,
        "p1",
        MemoryRetrievalRequest(
            purpose="coding_instruction", memory_types=["prompt_note"]
        ),
    )
    assert len(res.items) == 1
    assert res.policy_memory_types == ["prompt_note"]


def test_retrieve_includes_unapproved_when_requested():
    repo = InMemoryProjectMemoryCandidateRepository()
    repo.save(_make(memory_type="project_rule", status="proposed"))
    res = retrieve_memory(
        repo,
        "p1",
        MemoryRetrievalRequest(
            purpose="coding_instruction", include_approved_only=False
        ),
    )
    assert len(res.items) == 1


def test_retrieve_endpoint_returns_items(client, project):
    project_id = project["id"]
    memory_candidate_repo.save(
        _make(project_id=project_id, memory_type="project_rule")
    )
    memory_candidate_repo.save(
        _make(project_id=project_id, memory_type="coding_standard")
    )
    res = client.post(
        f"/projects/{project_id}/memory/retrieve",
        json={"purpose": "coding_instruction", "max_items": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert "project_rule" in body["policy_memory_types"]


def test_retrieve_endpoint_unknown_project_returns_404(client):
    res = client.post(
        "/projects/missing/memory/retrieve",
        json={"purpose": "coding_instruction"},
    )
    assert res.status_code == 404
