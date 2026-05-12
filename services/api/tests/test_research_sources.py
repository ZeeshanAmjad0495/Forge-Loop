from app.models import (
    ResearchBriefCreate,
    ResearchSourceCreate,
    ResearchSourceUpdate,
)
from app.repositories import (
    InMemoryResearchBriefRepository,
    InMemoryResearchSourceRepository,
)
from app.services.research_scout import create_brief
from app.services.research_sources import (
    attach_source_to_brief,
    create_source,
    update_source,
)


# -- service unit tests ----------------------------------------------------


def test_create_source_persists_and_defaults_accessed_at():
    repo = InMemoryResearchSourceRepository()
    source = create_source(
        repo,
        body=ResearchSourceCreate(
            title="OpenHands docs",
            source_type="docs",
            url="https://example.invalid/openhands",
        ),
    )
    assert source.title == "OpenHands docs"
    assert source.source_type == "docs"
    assert source.trust_level == "unknown"
    # accessed_at defaults to created_at when omitted
    assert source.accessed_at is not None
    assert repo.get(source.id) is source


def test_update_source_modifies_fields_only_in_body():
    repo = InMemoryResearchSourceRepository()
    source = create_source(
        repo,
        body=ResearchSourceCreate(title="t", source_type="paper", summary="a"),
    )
    updated = update_source(
        repo,
        source,
        ResearchSourceUpdate(
            summary="b", trust_level="high", tags=["llm", "eval"]
        ),
    )
    assert updated.summary == "b"
    assert updated.trust_level == "high"
    assert updated.tags == ["llm", "eval"]
    assert updated.title == "t"
    assert updated.source_type == "paper"


def test_attach_source_appends_and_dedups():
    brief_repo = InMemoryResearchBriefRepository()
    brief = create_brief(brief_repo, body=ResearchBriefCreate(title="x"))
    updated = attach_source_to_brief(brief_repo, brief, "src-1")
    assert updated.source_ids == ["src-1"]
    updated2 = attach_source_to_brief(brief_repo, updated, "src-2")
    assert updated2.source_ids == ["src-1", "src-2"]
    # idempotent on duplicate attachment
    updated3 = attach_source_to_brief(brief_repo, updated2, "src-1")
    assert updated3.source_ids == ["src-1", "src-2"]


# -- API tests --------------------------------------------------------------


def test_create_and_get_research_source(client):
    res = client.post(
        "/research-sources",
        json={
            "title": "Ollama README",
            "source_type": "docs",
            "url": "https://example.invalid/ollama",
            "summary": "Local-first runtime",
            "trust_level": "high",
            "key_points": ["runs locally"],
            "tags": ["local", "llm"],
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["trust_level"] == "high"

    fetched = client.get(f"/research-sources/{body['id']}").json()
    assert fetched["title"] == "Ollama README"
    assert fetched["key_points"] == ["runs locally"]


def test_list_research_sources_with_filters(client, project):
    project_id = project["id"]
    client.post(
        "/research-sources",
        json={
            "title": "paper a",
            "source_type": "paper",
            "trust_level": "high",
            "project_id": project_id,
            "tags": ["llm"],
        },
    )
    client.post(
        "/research-sources",
        json={
            "title": "blog b",
            "source_type": "blog",
            "trust_level": "low",
            "tags": ["misc"],
        },
    )

    all_sources = client.get("/research-sources").json()
    assert len(all_sources) == 2

    project_sources = client.get(
        f"/projects/{project_id}/research-sources"
    ).json()
    assert len(project_sources) == 1
    assert project_sources[0]["title"] == "paper a"

    papers = client.get("/research-sources?source_type=paper").json()
    assert len(papers) == 1

    high = client.get("/research-sources?trust_level=high").json()
    assert len(high) == 1

    by_tag = client.get("/research-sources?tag=llm").json()
    assert len(by_tag) == 1


def test_patch_research_source(client):
    created = client.post(
        "/research-sources",
        json={"title": "t", "source_type": "docs"},
    ).json()
    patched = client.patch(
        f"/research-sources/{created['id']}",
        json={"summary": "updated", "trust_level": "medium"},
    ).json()
    assert patched["summary"] == "updated"
    assert patched["trust_level"] == "medium"


def test_attach_source_to_brief_via_api(client):
    brief = client.post("/research-briefs", json={"title": "b"}).json()
    source = client.post(
        "/research-sources",
        json={"title": "s", "source_type": "docs"},
    ).json()
    res = client.post(
        f"/research-briefs/{brief['id']}/sources/{source['id']}"
    )
    assert res.status_code == 200
    assert source["id"] in res.json()["source_ids"]

    # idempotent
    res2 = client.post(
        f"/research-briefs/{brief['id']}/sources/{source['id']}"
    )
    assert res2.status_code == 200
    assert res2.json()["source_ids"].count(source["id"]) == 1


def test_attach_source_to_unknown_brief_404(client):
    source = client.post(
        "/research-sources",
        json={"title": "s", "source_type": "docs"},
    ).json()
    res = client.post(f"/research-briefs/missing/sources/{source['id']}")
    assert res.status_code == 404


def test_attach_unknown_source_to_brief_404(client):
    brief = client.post("/research-briefs", json={"title": "b"}).json()
    res = client.post(
        f"/research-briefs/{brief['id']}/sources/missing"
    )
    assert res.status_code == 404


def test_create_brief_with_existing_source_id_succeeds(client):
    source = client.post(
        "/research-sources",
        json={"title": "s", "source_type": "docs"},
    ).json()
    res = client.post(
        "/research-briefs",
        json={"title": "b", "source_ids": [source["id"]]},
    )
    assert res.status_code == 201
    assert source["id"] in res.json()["source_ids"]
