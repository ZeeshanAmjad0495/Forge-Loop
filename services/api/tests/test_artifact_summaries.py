import uuid
from datetime import datetime, timezone

from app.models import Artifact
from app.repositories import InMemoryArtifactSummaryRepository
from app.repositories_state import artifact_repo
from app.services.artifact_summaries import summarize_artifact


def _artifact(
    content: str = "hello world",
    artifact_type: str = "tool_run_result",
) -> Artifact:
    return Artifact(
        id=str(uuid.uuid4()),
        artifact_type=artifact_type,  # type: ignore[arg-type]
        content=content,
        created_at=datetime.now(timezone.utc),
    )


def test_summarize_short_content_completes():
    repo = InMemoryArtifactSummaryRepository()
    art = _artifact("hello\nworld\nfoo")
    summary = summarize_artifact(repo, art, summary_type="short")
    assert summary.status == "completed"
    assert summary.short_summary == "hello\nworld\nfoo"
    assert summary.structured_summary["line_count"] == 3
    assert summary.source_size_bytes == len(b"hello\nworld\nfoo")
    assert repo.get(summary.id) == summary


def test_summarize_truncates_large_content():
    repo = InMemoryArtifactSummaryRepository()
    art = _artifact("a" * 10_000)
    summary = summarize_artifact(repo, art, summary_type="agent_ready")
    assert summary.structured_summary["short_truncated"] is True
    assert summary.structured_summary["agent_ready_truncated"] is True
    assert len(summary.short_summary) == 800
    assert len(summary.agent_ready_summary) == 2000
    assert summary.compression_ratio > 0.0


def test_summarize_records_provider_without_calling_it():
    repo = InMemoryArtifactSummaryRepository()
    art = _artifact("x")
    summary = summarize_artifact(repo, art, provider="mock", model="mock-1")
    assert summary.provider == "mock"
    assert summary.model == "mock-1"


def test_repo_list_by_artifact_and_project():
    repo = InMemoryArtifactSummaryRepository()
    a1 = _artifact("a")
    a2 = _artifact("b")
    s1 = summarize_artifact(repo, a1, project_id="p1")
    s2 = summarize_artifact(repo, a1, project_id="p1")
    s3 = summarize_artifact(repo, a2, project_id="p2")
    assert {x.id for x in repo.list_by_artifact(a1.id)} == {s1.id, s2.id}
    assert {x.id for x in repo.list_by_project("p1")} == {s1.id, s2.id}
    assert {x.id for x in repo.list_by_project("p2")} == {s3.id}


# -- API tests --------------------------------------------------------------


def test_create_summary_for_missing_artifact_returns_404(client):
    res = client.post(
        "/artifacts/does-not-exist/summaries",
        json={"summary_type": "short"},
    )
    assert res.status_code == 404


def test_create_and_list_summary_via_api(client):
    art = _artifact("some content\nline two")
    artifact_repo.save(art)
    res = client.post(
        f"/artifacts/{art.id}/summaries",
        json={"summary_type": "short", "provider": "mock"},
    )
    assert res.status_code == 201
    created = res.json()
    assert created["artifact_id"] == art.id
    assert created["short_summary"].startswith("some content")

    listed = client.get(f"/artifacts/{art.id}/summaries").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    got = client.get(f"/artifact-summaries/{created['id']}").json()
    assert got["id"] == created["id"]


def test_get_artifact_summary_missing_returns_404(client):
    res = client.get("/artifact-summaries/missing")
    assert res.status_code == 404
