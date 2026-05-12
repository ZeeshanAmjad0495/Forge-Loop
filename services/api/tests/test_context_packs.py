from app.repositories import InMemoryContextPackRepository
from app.services.context_packs import create_context_pack, estimate_tokens


def test_estimate_tokens_simple():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1
    assert estimate_tokens("a" * 100) == 25


def test_create_context_pack_persists_with_estimate():
    repo = InMemoryContextPackRepository()
    pack = create_context_pack(
        repo,
        project_id="p1",
        source_type="dev_task",
        source_id="task-1",
        purpose="coding_instruction",
        provider="mock",
        model="m",
        content_summary="A" * 40,
        rules_summary="B" * 20,
        included_memory_ids=["mem-1"],
        included_artifact_ids=["art-1"],
    )
    assert pack.estimated_tokens == 10 + 5
    assert pack.included_memory_ids == ["mem-1"]
    assert pack.included_artifact_ids == ["art-1"]
    assert repo.get(pack.id) == pack


def test_create_context_pack_respects_explicit_estimate():
    repo = InMemoryContextPackRepository()
    pack = create_context_pack(
        repo,
        project_id="p1",
        source_type="ci_event",
        source_id="ci-1",
        purpose="ci_analysis",
        estimated_tokens_value=500,
    )
    assert pack.estimated_tokens == 500


def test_repo_list_by_project_and_source_and_target():
    repo = InMemoryContextPackRepository()
    create_context_pack(
        repo,
        project_id="p1",
        source_type="dev_task",
        source_id="t1",
        target_type="agent_run",
        target_id="r1",
        purpose="coding_instruction",
    )
    create_context_pack(
        repo,
        project_id="p1",
        source_type="dev_task",
        source_id="t1",
        target_type="agent_run",
        target_id="r2",
        purpose="coding_instruction",
    )
    create_context_pack(
        repo,
        project_id="p2",
        source_type="dev_task",
        source_id="t1",
        target_type="agent_run",
        target_id="r3",
        purpose="coding_instruction",
    )
    assert len(repo.list_by_project("p1")) == 2
    assert len(repo.list_by_source("dev_task", "t1")) == 3
    assert len(repo.list_by_target("agent_run", "r1")) == 1


def test_list_context_packs_for_unknown_project_returns_404(client):
    res = client.get("/projects/missing/context-packs")
    assert res.status_code == 404


def test_create_and_list_context_pack(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/context-packs",
        json={
            "source_type": "dev_task",
            "source_id": "t1",
            "purpose": "coding_instruction",
            "content_summary": "summary",
            "included_memory_ids": ["m1"],
            "included_artifact_ids": ["a1"],
        },
    )
    assert res.status_code == 201
    pack = res.json()
    assert pack["project_id"] == project_id
    assert pack["estimated_tokens"] >= 1

    listed = client.get(f"/projects/{project_id}/context-packs").json()
    assert len(listed) == 1
    assert listed[0]["id"] == pack["id"]


def test_get_context_pack_missing_returns_404(client):
    res = client.get("/context-packs/missing-id")
    assert res.status_code == 404


def test_list_context_packs_by_source_filter(client, project):
    project_id = project["id"]
    client.post(
        f"/projects/{project_id}/context-packs",
        json={
            "source_type": "dev_task",
            "source_id": "t1",
            "purpose": "coding_instruction",
        },
    )
    client.post(
        f"/projects/{project_id}/context-packs",
        json={
            "source_type": "ci_event",
            "source_id": "ci1",
            "purpose": "ci_analysis",
        },
    )
    res = client.get(
        f"/projects/{project_id}/context-packs",
        params={"source_type": "dev_task", "source_id": "t1"},
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["source_type"] == "dev_task"
