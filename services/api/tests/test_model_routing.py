import pytest

from app import config
from app.services.model_routing import (
    ModelRoutePreviewRequest,
    decide_route,
    routing_summary,
)


def test_test_workflow_routes_to_mock():
    decision = decide_route(ModelRoutePreviewRequest(workflow_type="test"))
    assert decision.selected_provider == "mock"
    assert decision.reason == "test_smoke_demo_workflow"


def test_requirement_analysis_routes_to_deepseek():
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="requirement_analysis")
    )
    assert decision.selected_provider == "deepseek"
    assert decision.fallback_provider == "kimi"


def test_long_context_routes_to_kimi():
    decision = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="pr_review", estimated_context_tokens=200_000
        )
    )
    assert decision.selected_provider == "kimi"
    assert decision.reason == "long_context_threshold_exceeded"


def test_explicit_workflow_long_context_review():
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="long_context_review")
    )
    assert decision.selected_provider == "kimi"


def test_high_risk_requires_human_approval():
    decision = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="pr_review", risk_level="high"
        )
    )
    assert decision.requires_human_approval is True
    assert decision.reason == "high_risk_workflow"


def test_artifact_summary_without_ollama_falls_back(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", False)
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="artifact_summary")
    )
    assert decision.selected_provider == "deepseek"
    assert "ollama_not_enabled_falling_back_to_reasoning_provider" in decision.warnings


def test_artifact_summary_with_ollama_enabled(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_ENABLED", True)
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="artifact_summary")
    )
    assert decision.selected_provider == "ollama"


def test_explicit_override_respected():
    decision = decide_route(
        ModelRoutePreviewRequest(
            workflow_type="requirement_analysis",
            override_provider="kimi",
            override_model="moonshot-v1-128k",
        )
    )
    assert decision.selected_provider == "kimi"
    assert decision.selected_model == "moonshot-v1-128k"
    assert decision.reason == "explicit_override"


def test_routing_disabled_uses_global(monkeypatch):
    monkeypatch.setattr(config, "MODEL_ROUTING_ENABLED", False)
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    decision = decide_route(
        ModelRoutePreviewRequest(workflow_type="requirement_analysis")
    )
    assert decision.selected_provider == "mock"
    assert decision.reason == "routing_disabled_use_global_llm_provider"


def test_routing_summary_returns_keys():
    summary = routing_summary()
    assert "enabled" in summary
    assert "default_reasoning_provider" in summary
    assert "long_context_threshold_tokens" in summary


# -- API tests --------------------------------------------------------------


def test_model_route_preview_endpoint(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/model-route/preview",
        json={"workflow_type": "requirement_analysis"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["selected_provider"] == "deepseek"
    assert body["project_id"] == project_id


def test_model_route_preview_unknown_project(client):
    res = client.post(
        "/projects/missing/model-route/preview",
        json={"workflow_type": "requirement_analysis"},
    )
    assert res.status_code == 404


def test_runtime_model_routing_endpoint(client):
    res = client.get("/runtime/model-routing")
    assert res.status_code == 200
    body = res.json()
    assert "enabled" in body
