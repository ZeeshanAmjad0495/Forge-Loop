"""Task 81: controlled vector retrieval tests. No external vector DB."""

import sys

import pytest

from app import config
from app.services import vector_store as vs
from app.services.contextpack_builder import (
    ContextPackBuildRequest,
    build_context_pack,
)
from app.services.vector_store import (
    MemoryVectorStore,
    VectorDocument,
    retrieve_for_context,
)


def _doc(did, pid, kind, sid, text):
    return VectorDocument(
        document_id=did,
        project_id=pid,
        kind=kind,
        source_type="memory",
        source_id=sid,
        text=text,
    )


def test_index_and_query_returns_source_ids_deterministically():
    store = MemoryVectorStore()
    store.index(_doc("d1", "p1", "project_memory", "m1", "auth login token"))
    store.index(_doc("d2", "p1", "project_memory", "m2", "database backup"))
    res = store.query("p1", "login token auth")
    assert [m.source_id for m in res] == ["m1"]
    assert res[0].kind == "project_memory"
    # Deterministic on repeat.
    assert store.query("p1", "login token auth")[0].document_id == "d1"


def test_top_k_bound():
    store = MemoryVectorStore()
    for i in range(10):
        store.index(_doc(f"d{i}", "p1", "human_feedback", f"f{i}", "alpha beta"))
    assert len(store.query("p1", "alpha beta", top_k=3)) == 3
    assert store.query("p1", "alpha beta", top_k=0) == []


def test_snippet_bounded_by_chunk_tokens(monkeypatch):
    monkeypatch.setattr(config, "VECTOR_MAX_CHUNK_TOKENS", 5)
    store = MemoryVectorStore()
    store.index(_doc("d1", "p1", "ci_lesson", "c1", "word " * 200))
    m = store.query("p1", "word")[0]
    assert "[truncated]" in m.snippet
    assert len(m.snippet) <= 5 * 4 + len("\n…[truncated]")


def test_refused_and_unknown_kinds():
    store = MemoryVectorStore()
    with pytest.raises(ValueError, match="never indexed"):
        store.index(_doc("d", "p", "secret", "s", "x"))
    with pytest.raises(ValueError, match="never indexed"):
        store.index(_doc("d", "p", "code", "s", "x"))
    with pytest.raises(ValueError, match="not an indexable summary kind"):
        store.index(_doc("d", "p", "random_kind", "s", "x"))


def test_raw_artifact_refused_by_default():
    store = MemoryVectorStore()
    with pytest.raises(ValueError):
        store.index(_doc("d", "p", "raw_artifact", "a1", "blob"))


def test_project_scoped():
    store = MemoryVectorStore()
    store.index(_doc("d1", "pA", "project_memory", "m1", "shared term"))
    store.index(_doc("d2", "pB", "project_memory", "m2", "shared term"))
    res = store.query("pA", "shared term")
    assert [m.project_id for m in res] == ["pA"]


def test_delete_by_source_and_count():
    store = MemoryVectorStore()
    store.index(_doc("d1", "p1", "project_memory", "m1", "x y"))
    store.index(_doc("d2", "p1", "incident_lesson", "i1", "x y"))
    assert store.count("p1") == 2
    assert store.delete_by_source("memory", "m1") == 1
    assert store.count("p1") == 1


def test_factory_default_and_unknown(monkeypatch):
    assert "chromadb" not in sys.modules
    monkeypatch.setattr(config, "VECTOR_PROVIDER", "memory")
    vs.reset_vector_store()
    assert isinstance(vs.get_vector_store(), MemoryVectorStore)
    monkeypatch.setattr(config, "VECTOR_PROVIDER", "chroma")
    vs.reset_vector_store()
    with pytest.raises(RuntimeError, match="not implemented yet"):
        vs.get_vector_store()
    assert "chromadb" not in sys.modules
    monkeypatch.setattr(config, "VECTOR_PROVIDER", "weird")
    vs.reset_vector_store()
    with pytest.raises(RuntimeError, match="Unsupported VECTOR_PROVIDER"):
        vs.get_vector_store()


def test_disabled_by_default():
    # Default config: retrieval is OFF even with indexed docs.
    assert config.VECTOR_RETRIEVAL_ENABLED is False
    vs.get_vector_store().index(
        _doc("d1", "p1", "project_memory", "m1", "alpha")
    )
    assert retrieve_for_context("p1", "alpha") == ("", [])


def test_retrieve_for_context_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "VECTOR_RETRIEVAL_ENABLED", True)
    vs.get_vector_store().index(
        _doc("d1", "p1", "architecture_decision", "adr-1", "use postgres")
    )
    text, sources = retrieve_for_context("p1", "postgres decision")
    assert "adr-1" in sources
    assert "use postgres" in text


def test_contextpack_retrieval_gated(monkeypatch, client):
    pr = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    pid = pr["id"]
    vs.get_vector_store().index(
        _doc("d1", pid, "project_memory", "mem-9", "billing edge case")
    )
    body = ContextPackBuildRequest(
        active_task_context="work",
        use_retrieval=True,
        retrieval_query="billing edge case",
    )
    # Disabled by default -> no retrieval.
    r_off = build_context_pack(project_id=pid, body=body, persist=False)
    assert r_off.retrieved_memory == ""
    assert r_off.retrieved_source_ids == []
    # Enabled + opted in -> retrieval included.
    monkeypatch.setattr(config, "VECTOR_RETRIEVAL_ENABLED", True)
    r_on = build_context_pack(project_id=pid, body=body, persist=False)
    assert "mem-9" in r_on.retrieved_source_ids
    assert "billing edge case" in r_on.retrieved_memory


def test_runtime_vector_route(client):
    res = client.get("/runtime/vector")
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is False
    assert data["active_backend"] == "memory"
    assert data["is_source_of_truth"] is False
    assert len(data["indexable_kinds"]) == 7
