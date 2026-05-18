"""Task 89 — ContextPack enforced across model-facing workflows.

A compact ContextPack is built, persisted, and linked at the routed
chokepoint before every real model call. Oversized raw context warns by
default and hard-blocks when CONTEXTPACK_BLOCK_OVERSIZED is set. The mock
no-provider profile and the enforcement-disabled escape hatch skip it.
No real providers / keys / network.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories_state import context_pack_repo, project_repo
from app.services.model_routing import RoutedProviderError, resolve_routed_provider

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    from app.repositories_state import repos

    repos.reset_all()
    yield


def _project() -> str:
    res = client.post(
        "/projects",
        json={"name": "CtxProj", "description": "a project with context"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_real_routed_call_links_context_pack(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    pid = _project()
    _, decision = resolve_routed_provider(
        "planning", project_id=pid, source_id="ticket-1"
    )
    assert decision.context_pack_id is not None
    pack = context_pack_repo.get(decision.context_pack_id)
    assert pack is not None
    assert pack.project_id == pid


def test_mock_profile_skips_context_pack(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    pid = _project()
    _, decision = resolve_routed_provider("planning", project_id=pid)
    assert decision.context_pack_id is None
    assert context_pack_repo.list_by_project(pid) == []


def test_enforcement_disabled_skips_context_pack(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "CONTEXTPACK_ENFORCED", False)
    pid = _project()
    _, decision = resolve_routed_provider("planning", project_id=pid)
    assert decision.context_pack_id is None


def test_oversized_context_warns_by_default(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "CONTEXTPACK_DEFAULT_TOKEN_BUDGET", 1)
    monkeypatch.setattr(config, "CONTEXTPACK_MAX_TOKEN_BUDGET", 1)
    monkeypatch.setattr(config, "CONTEXTPACK_BLOCK_OVERSIZED", False)
    pid = _project()
    _, decision = resolve_routed_provider("planning", project_id=pid)
    assert "contextpack_oversized_reduced_to_budget" in decision.warnings
    assert decision.context_pack_id is not None  # still produced


def test_oversized_context_blocks_when_configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "CONTEXTPACK_DEFAULT_TOKEN_BUDGET", 1)
    monkeypatch.setattr(config, "CONTEXTPACK_MAX_TOKEN_BUDGET", 1)
    monkeypatch.setattr(config, "CONTEXTPACK_BLOCK_OVERSIZED", True)
    pid = _project()
    with pytest.raises(RoutedProviderError):
        resolve_routed_provider("planning", project_id=pid)


def test_no_project_id_skips_context_pack(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    _, decision = resolve_routed_provider("planning")
    assert decision.context_pack_id is None


def test_workflow_purpose_mapping():
    from app.services.model_routing import _context_purpose_for

    assert _context_purpose_for("ci_analysis") == "ci_analysis"
    assert _context_purpose_for("memory_extraction") == "memory_learning"
    assert _context_purpose_for("planning") == "custom"
    assert _context_purpose_for("review") == "pr_review"
