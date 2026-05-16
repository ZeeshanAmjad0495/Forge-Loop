"""Task 78: layered ContextPack + token-budget reduction.

Deterministic — no provider is invoked (compression provider is only
recorded). Reduction is structural truncate-then-drop."""

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services.contextpack_builder import (
    ContextPackBuildRequest,
    build_context_pack,
)

client = TestClient(app)


def _project():
    return client.post(
        "/projects", json={"name": "CP78", "description": "ctx test"}
    ).json()


# 1. Includes key project/task fields.
def test_pack_includes_key_fields():
    p = _project()
    res = build_context_pack(
        project_id=p["id"],
        body=ContextPackBuildRequest(
            purpose="coding_instruction",
            active_task_context="implement /metrics endpoint",
            relevant_requirements="req: expose monitoring summary",
            source_ids=["dt-1"],
        ),
        persist=False,
    )
    assert "CP78" in res.project_profile  # autofilled from project
    assert res.active_task_context.startswith("implement /metrics")
    assert res.relevant_requirements
    assert res.source_ids == ["dt-1"]


# 2 & 3. Respects token budget; large context triggers reduction+warning.
def test_large_context_reduced_to_budget():
    p = _project()
    big = "x " * 20000  # ~ huge
    res = build_context_pack(
        project_id=p["id"],
        body=ContextPackBuildRequest(
            token_budget=500,
            active_task_context=big,
            relevant_artifacts=big,
            recent_decisions=big,
        ),
        persist=False,
    )
    assert res.estimated_tokens <= 500 or res.compression_level == "aggressive"
    assert res.compression_level in ("light", "aggressive")
    assert res.excluded_context_reasoning  # recorded what was cut


def test_max_budget_cap_enforced():
    p = _project()
    res = build_context_pack(
        project_id=p["id"],
        body=ContextPackBuildRequest(token_budget=999999),
        persist=False,
    )
    assert res.token_budget == config.CONTEXTPACK_MAX_TOKEN_BUDGET


# 4. Ollama preferred for compression when enabled.
def test_ollama_preferred_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(config, "CONTEXTPACK_COMPRESSION_PROVIDER", "ollama")
    p = _project()
    res = build_context_pack(
        project_id=p["id"], body=ContextPackBuildRequest(), persist=False
    )
    assert res.compression_provider == "ollama"


# 5. DeepSeek fallback when Ollama disabled.
def test_deepseek_fallback_when_ollama_disabled(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", False)
    monkeypatch.setattr(config, "CONTEXTPACK_COMPRESSION_PROVIDER", "ollama")
    monkeypatch.setattr(config, "CONTEXTPACK_FALLBACK_PROVIDER", "deepseek")
    p = _project()
    res = build_context_pack(
        project_id=p["id"], body=ContextPackBuildRequest(), persist=False
    )
    assert res.compression_provider == "deepseek"
    assert any("fallback" in w for w in res.warnings)


# 6. Kimi never used for compression even if misconfigured.
def test_kimi_never_used_for_compression(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(config, "CONTEXTPACK_COMPRESSION_PROVIDER", "kimi")
    p = _project()
    res = build_context_pack(
        project_id=p["id"], body=ContextPackBuildRequest(), persist=False
    )
    assert res.compression_provider != "kimi"
    assert res.compression_provider == "deepseek"
    assert any("kimi_not_allowed" in w for w in res.warnings)


# 7. Deterministic output for identical input + cache hit on 2nd call.
def test_deterministic_and_cached(monkeypatch):
    monkeypatch.setattr(config, "CONTEXTPACK_CACHE_ENABLED", True)
    p = _project()
    body = ContextPackBuildRequest(
        purpose="pr_review", source_type="pr_draft", source_id="d1",
        active_task_context="same content", source_ids=["a", "b"],
    )
    r1 = build_context_pack(project_id=p["id"], body=body)
    r2 = build_context_pack(project_id=p["id"], body=body)
    assert r1.estimated_tokens == r2.estimated_tokens
    assert r1.compression_level == r2.compression_level
    assert r2.cached is True


# Route + persistence.
def test_build_route_persists_pack():
    p = _project()
    r = client.post(
        f"/projects/{p['id']}/context-packs/build",
        json={"purpose": "coding_instruction",
              "active_task_context": "do X", "source_ids": ["dt9"]},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["context_pack_id"]
    packs = client.get(f"/projects/{p['id']}/context-packs").json()
    got = [c for c in packs if c["id"] == d["context_pack_id"]]
    assert got and got[0]["source_ids"] == ["dt9"]


def test_disabled_passthrough(monkeypatch):
    monkeypatch.setattr(config, "CONTEXTPACK_ENABLED", False)
    p = _project()
    res = build_context_pack(
        project_id=p["id"],
        body=ContextPackBuildRequest(active_task_context="hi"),
        persist=False,
    )
    assert res.compression_level == "none"
    assert any("disabled" in w for w in res.warnings)
