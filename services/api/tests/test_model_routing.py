"""#46: model-routing hardening — Kimi is a gated expensive fallback,
never an automatic default. Covers the 10 required policy cases."""

import pytest

from app import config
from app.llm import _PROVIDER_REGISTRY
from app.services.model_routing import (
    ModelRoutePreviewRequest,
    decide_route,
    routing_summary,
)


# 1. Local workflow -> Ollama when OLLAMA_ENABLED=true
def test_local_workflow_routes_to_ollama_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(config, "MODEL_ROUTING_PREFER_LOCAL", True)
    d = decide_route(ModelRoutePreviewRequest(workflow_type="artifact_summary"))
    assert d.selected_provider == config.LOCAL_CHEAP_PROVIDER == "ollama"


# 2. Local workflow -> DeepSeek when Ollama disabled
def test_local_workflow_falls_back_to_deepseek_when_ollama_off(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", False)
    d = decide_route(ModelRoutePreviewRequest(workflow_type="memory_extraction"))
    assert d.selected_provider == "deepseek"
    assert "ollama_disabled_falling_back_to_deepseek_not_kimi" in d.warnings


# 3. Local workflow never routes to Kimi by default
@pytest.mark.parametrize("enabled", [True, False])
def test_local_workflow_never_kimi_by_default(monkeypatch, enabled):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", enabled)
    d = decide_route(ModelRoutePreviewRequest(workflow_type="classification"))
    assert d.selected_provider != "kimi"
    assert "kimi" not in d.fallback_chain


# 4. Normal reasoning -> DeepSeek
def test_normal_reasoning_routes_to_deepseek():
    d = decide_route(ModelRoutePreviewRequest(workflow_type="planning"))
    assert d.selected_provider == "deepseek"
    assert d.reason == "default_reasoning_workflow"


# 5. Normal reasoning fallback chain does not put Kimi first
def test_reasoning_fallback_chain_not_kimi_first():
    d = decide_route(ModelRoutePreviewRequest(workflow_type="coding"))
    assert d.fallback_chain[0] == "deepseek"
    assert "kimi" not in d.fallback_chain  # default: no expensive opt-in


# 6. Long context not routed to Kimi unless expensive allowed
def test_long_context_not_kimi_by_default():
    d = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="long_context_review",
            estimated_context_tokens=200000,
        )
    )
    assert d.selected_provider == "deepseek"
    assert d.selected_provider != "kimi"


def test_long_context_kimi_when_expensive_explicitly_allowed():
    d = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="long_context_review",
            allow_expensive_provider=True,
            expensive_approved=True,
        )
    )
    assert d.selected_provider == "kimi"


# 7. Long context returns context-reduction recommendation/warning
def test_long_context_recommends_context_reduction(monkeypatch):
    monkeypatch.setattr(config, "MODEL_ROUTING_CONTEXT_REDUCTION_FIRST", True)
    d = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="long_context_review",
            estimated_context_tokens=999999,
        )
    )
    assert d.context_reduction_recommended is True
    assert any("context_reduction" in w for w in d.warnings)


# 8. High risk requires approval but not Kimi by default
def test_high_risk_requires_approval_but_not_kimi():
    d = decide_route(
        ModelRoutePreviewRequest(workflow_type="coding", risk_level="high")
    )
    assert d.requires_human_approval is True
    assert d.selected_provider == "deepseek"
    assert d.selected_provider != "kimi"


# 9. Explicit Kimi override blocked / approval-required when required
def test_explicit_kimi_override_blocked_when_approval_required(monkeypatch):
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "KIMI_AUTO_FALLBACK_ENABLED", False)
    d = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="planning", override_provider="kimi"
        )
    )
    assert d.selected_provider != "kimi"
    assert d.expensive_provider_blocked is True
    assert d.requires_human_approval is True


def test_explicit_kimi_override_allowed_when_approved():
    d = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="planning", override_provider="kimi",
            allow_expensive_provider=True, expensive_approved=True,
        )
    )
    assert d.selected_provider == "kimi"
    assert d.expensive_provider_blocked is False


# 10. Provider/model defaults consistent across llm + model_routing
def test_provider_model_defaults_consistent(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODEL", None)
    from app.services.model_routing import _model_for

    for name, meta in _PROVIDER_REGISTRY.items():
        assert _model_for(name) == meta["default_model"]


# --- endpoint smoke (kept; summary keys updated to new schema) -----------

def test_routing_summary_keys():
    s = routing_summary()
    for k in (
        "normal_reasoning_provider", "expensive_provider",
        "local_cheap_provider", "kimi_require_approval",
        "context_reduction_first",
    ):
        assert k in s


def test_model_route_preview_endpoint(client, project):
    res = client.post(
        f"/projects/{project['id']}/model-route/preview",
        json={"workflow_type": "planning"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["selected_provider"] == "deepseek"
    assert "fallback_chain" in body


def test_model_route_preview_unknown_project(client):
    res = client.post(
        "/projects/nope/model-route/preview",
        json={"workflow_type": "planning"},
    )
    assert res.status_code == 404


def test_runtime_model_routing_endpoint(client):
    res = client.get("/runtime/model-routing")
    assert res.status_code == 200
    assert res.json()["expensive_provider"] == "kimi"
