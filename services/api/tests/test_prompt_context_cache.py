from app.repositories import InMemoryPromptContextCacheRepository
from app.services.prompt_context_cache import (
    compute_cache_key,
    content_hash,
    get_cached,
    record_hit,
    set_cached,
)


def test_compute_cache_key_is_stable_for_same_inputs():
    k1 = compute_cache_key(
        project_id="p1",
        cache_type="prompt_prefix",
        source_type="dev_task",
        source_id="t1",
        content_hash_value="abc",
    )
    k2 = compute_cache_key(
        project_id="p1",
        cache_type="prompt_prefix",
        source_type="dev_task",
        source_id="t1",
        content_hash_value="abc",
    )
    assert k1 == k2


def test_compute_cache_key_differs_for_different_content():
    k1 = compute_cache_key(
        project_id="p1",
        cache_type="prompt_prefix",
        content_hash_value="abc",
    )
    k2 = compute_cache_key(
        project_id="p1",
        cache_type="prompt_prefix",
        content_hash_value="xyz",
    )
    assert k1 != k2


def test_set_and_get_cached_by_key():
    repo = InMemoryPromptContextCacheRepository()
    entry = set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="hello world",
        summary="hi",
        source_type="dev_task",
        source_id="t1",
        estimated_tokens=10,
    )
    assert entry.content_hash == content_hash("hello world")

    fetched = get_cached(repo, entry.cache_key)
    assert fetched is not None
    assert fetched.id == entry.id


def test_set_cached_with_same_inputs_updates_existing():
    repo = InMemoryPromptContextCacheRepository()
    e1 = set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="v",
    )
    e2 = set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="v",
    )
    assert e1.id == e2.id
    assert len(repo.list_by_project("p1")) == 1


def test_record_hit_increments_count():
    repo = InMemoryPromptContextCacheRepository()
    entry = set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="v",
    )
    record_hit(repo, entry)
    record_hit(repo, entry)
    fetched = repo.get(entry.id)
    assert fetched is not None
    assert fetched.hit_count == 2
    assert fetched.last_used_at is not None


def test_list_by_project_and_source():
    repo = InMemoryPromptContextCacheRepository()
    set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="v1",
        source_type="dev_task",
        source_id="t1",
    )
    set_cached(
        repo,
        project_id="p1",
        cache_type="prompt_prefix",
        value="v2",
        source_type="dev_task",
        source_id="t2",
    )
    set_cached(
        repo,
        project_id="p2",
        cache_type="prompt_prefix",
        value="v3",
    )
    assert len(repo.list_by_project("p1")) == 2
    assert len(repo.list_by_source("dev_task", "t1")) == 1


# -- API tests --------------------------------------------------------------


def test_list_cache_for_unknown_project_returns_404(client):
    res = client.get("/projects/missing/prompt-context-cache")
    assert res.status_code == 404


def test_list_and_get_via_api(client, project):
    project_id = project["id"]
    from app.repositories_state import prompt_cache_repo

    entry = set_cached(
        prompt_cache_repo,
        project_id=project_id,
        cache_type="prompt_prefix",
        value="value",
        summary="sum",
    )
    res = client.get(f"/projects/{project_id}/prompt-context-cache")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == entry.id

    got = client.get(f"/prompt-context-cache/{entry.id}").json()
    assert got["id"] == entry.id


def test_delete_cache_entry(client, project):
    project_id = project["id"]
    from app.repositories_state import prompt_cache_repo

    entry = set_cached(
        prompt_cache_repo,
        project_id=project_id,
        cache_type="prompt_prefix",
        value="v",
    )
    res = client.delete(f"/prompt-context-cache/{entry.id}")
    assert res.status_code == 204
    assert client.get(f"/prompt-context-cache/{entry.id}").status_code == 404
