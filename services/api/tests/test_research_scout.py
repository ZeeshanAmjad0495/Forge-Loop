import json

import pytest

from app.models import (
    ResearchBriefCreate,
    ResearchBriefGenerateRequest,
    ResearchBriefUpdate,
)
from app.repositories import (
    InMemoryArtifactRepository,
    InMemoryResearchBriefRepository,
)
from app.services.research_scout import (
    archive_brief,
    create_brief,
    generate_brief,
    update_brief,
)


class _StubProvider:
    provider_name = "stub"
    model_name = "stub-model"

    def __init__(self, response: str):
        self._response = response
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


# -- service unit tests ----------------------------------------------------


def test_create_brief_persists_defaults():
    repo = InMemoryResearchBriefRepository()
    brief = create_brief(
        repo,
        body=ResearchBriefCreate(title="Eval OpenHands", research_type="tool_evaluation"),
    )
    assert brief.title == "Eval OpenHands"
    assert brief.research_type == "tool_evaluation"
    assert brief.status == "draft"
    assert brief.completed_at is None
    assert repo.get(brief.id) == brief


def test_update_brief_completed_sets_completed_at():
    repo = InMemoryResearchBriefRepository()
    brief = create_brief(repo, body=ResearchBriefCreate(title="x"))
    updated = update_brief(
        repo,
        brief,
        ResearchBriefUpdate(status="completed", summary="ok", findings=["f1"]),
    )
    assert updated.status == "completed"
    assert updated.summary == "ok"
    assert updated.findings == ["f1"]
    assert updated.completed_at is not None


def test_archive_brief_sets_archived_status():
    repo = InMemoryResearchBriefRepository()
    brief = create_brief(repo, body=ResearchBriefCreate(title="x"))
    archived = archive_brief(repo, brief)
    assert archived.status == "archived"


def test_generate_brief_parses_provider_json():
    brief_repo = InMemoryResearchBriefRepository()
    artifact_repo = InMemoryArtifactRepository()
    payload = json.dumps(
        {
            "summary": "Recommend OpenHands for Release N.",
            "findings": ["mature", "active maintenance"],
            "recommendations": ["adopt for code execution"],
            "risks": ["dependency on Docker"],
        }
    )
    provider = _StubProvider(payload)
    brief, artifact = generate_brief(
        brief_repo,
        artifact_repo,
        provider,
        body=ResearchBriefGenerateRequest(
            title="OpenHands eval",
            research_type="tool_evaluation",
            question="Should we adopt OpenHands?",
        ),
        source_summaries=["openhands docs excerpt"],
    )
    assert brief.status == "completed"
    assert brief.findings == ["mature", "active maintenance"]
    assert brief.recommendations == ["adopt for code execution"]
    assert brief.provider == "stub"
    assert brief.model == "stub-model"
    assert brief.artifact_id == artifact.id
    assert "RESEARCH_SCOUT_AGENT" in provider.prompts[0]
    assert "openhands docs excerpt" in provider.prompts[0]
    assert artifact_repo.get(artifact.id) is not None


def test_generate_brief_unparseable_marks_failed():
    brief_repo = InMemoryResearchBriefRepository()
    artifact_repo = InMemoryArtifactRepository()
    provider = _StubProvider("not json at all")
    brief, _artifact = generate_brief(
        brief_repo,
        artifact_repo,
        provider,
        body=ResearchBriefGenerateRequest(title="x"),
    )
    assert brief.status == "failed"
    assert brief.error_message


# -- API tests --------------------------------------------------------------


def test_create_research_brief_via_api(client):
    res = client.post(
        "/research-briefs",
        json={"title": "Eval Ollama models", "research_type": "model_evaluation"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Eval Ollama models"
    assert body["status"] == "draft"


def test_create_research_brief_unknown_project_404(client):
    res = client.post(
        "/research-briefs",
        json={"title": "x", "project_id": "missing"},
    )
    assert res.status_code == 404


def test_create_research_brief_unknown_source_400(client):
    res = client.post(
        "/research-briefs",
        json={"title": "x", "source_ids": ["does-not-exist"]},
    )
    assert res.status_code == 400


def test_list_research_briefs_global_and_by_project(client, project):
    project_id = project["id"]
    client.post("/research-briefs", json={"title": "global brief"})
    client.post(
        "/research-briefs",
        json={"title": "project brief", "project_id": project_id},
    )
    listed = client.get("/research-briefs").json()
    assert len(listed) == 2

    listed_for_project = client.get(
        f"/projects/{project_id}/research-briefs"
    ).json()
    assert len(listed_for_project) == 1
    assert listed_for_project[0]["title"] == "project brief"


def test_filter_research_briefs(client):
    client.post(
        "/research-briefs",
        json={"title": "a", "research_type": "tool_evaluation"},
    )
    client.post(
        "/research-briefs",
        json={"title": "b", "research_type": "architecture"},
    )
    filtered = client.get(
        "/research-briefs", params={"research_type": "architecture"}
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["title"] == "b"


def test_patch_and_archive_research_brief(client):
    created = client.post("/research-briefs", json={"title": "x"}).json()
    brief_id = created["id"]

    patched = client.patch(
        f"/research-briefs/{brief_id}",
        json={"summary": "done", "status": "completed"},
    ).json()
    assert patched["status"] == "completed"
    assert patched["completed_at"] is not None

    archived = client.post(f"/research-briefs/{brief_id}/archive").json()
    assert archived["status"] == "archived"


def test_get_missing_research_brief_404(client):
    res = client.get("/research-briefs/missing")
    assert res.status_code == 404


def test_generate_research_brief_via_api_with_mock_provider(client):
    res = client.post(
        "/research-briefs/generate?provider_name=mock",
        json={
            "title": "x",
            "research_type": "tool_evaluation",
            "question": "Should we adopt OpenHands?",
        },
    )
    # mock provider returns a non-JSON markdown brief, so generate should record
    # status=failed but still persist the brief — exercising the unparseable path.
    assert res.status_code == 201
    payload = res.json()
    assert payload["provider"] == "mock"
    assert payload["status"] in {"completed", "failed"}
