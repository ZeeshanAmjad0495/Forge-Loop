"""Task 87 — enforce ModelRouter everywhere.

Proves there is no hidden provider selection: every real LLM call
resolves its provider through ``resolve_routed_provider`` (the enforced
ModelRouter entrypoint), the keyless mock default is honored, the
expensive (Kimi) provider stays gated, and no route/service module
selects a provider directly.
"""

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services.model_routing import (
    RoutedProviderError,
    resolve_routed_provider,
)

client = TestClient(app)

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

# Direct provider selection is allowed ONLY in the provider factory and
# the router itself (factory internals) plus the informational
# GET /llm/providers endpoint which makes no LLM call.
_ALLOWED_DIRECT = {
    APP_DIR / "llm" / "__init__.py",
    APP_DIR / "services" / "model_routing.py",
    APP_DIR / "routes" / "llm.py",
}


def test_no_route_or_service_selects_provider_directly():
    """Structural no-bypass guard."""
    offenders = []
    for path in list((APP_DIR / "routes").glob("*.py")) + list(
        (APP_DIR / "services").glob("*.py")
    ):
        if path in _ALLOWED_DIRECT:
            continue
        text = path.read_text()
        if "get_provider_by_name" in text or "get_default_provider_name" in text:
            offenders.append(str(path.relative_to(APP_DIR)))
    assert offenders == [], (
        f"These modules bypass the ModelRouter by selecting a provider "
        f"directly: {offenders}"
    )


def test_mock_default_is_honored_in_keyless_env():
    """Local/test profile (LLM_PROVIDER=mock) must not route to a hosted
    provider — there are no API keys."""
    provider, decision = resolve_routed_provider("planning")
    assert provider.provider_name == "mock"
    assert decision.selected_provider == "mock"
    assert decision.reason == "global_default_provider_is_mock_no_real_providers"


def test_real_routing_when_default_provider_configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    _, decision = resolve_routed_provider("planning")
    assert decision.selected_provider == config.NORMAL_REASONING_PROVIDER
    assert decision.selected_provider == "deepseek"


def test_kimi_override_blocked_without_approval(monkeypatch):
    """A per-request kimi override must NOT reach Kimi unless the route
    decision allows expensive use."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "KIMI_AUTO_FALLBACK_ENABLED", False)
    provider, decision = resolve_routed_provider(
        "planning", provider_override="kimi"
    )
    assert decision.selected_provider != "kimi"
    assert provider.provider_name != "kimi"
    assert decision.expensive_provider_blocked is True


def test_kimi_override_honored_when_allowed_and_approved(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "KIMI_API_KEY", "offline-test-key")
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "KIMI_AUTO_FALLBACK_ENABLED", False)
    provider, decision = resolve_routed_provider(
        "planning",
        provider_override="kimi",
        allow_expensive_provider=True,
        expensive_approved=True,
    )
    assert decision.selected_provider == "kimi"
    assert provider.provider_name == "kimi"


def test_enforcement_disabled_restores_legacy_path(monkeypatch):
    monkeypatch.setattr(config, "MODEL_ROUTING_ENFORCED", False)
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    provider, decision = resolve_routed_provider(
        "planning", provider_override="deepseek"
    )
    assert decision.selected_provider == "deepseek"
    assert decision.reason == "routing_enforcement_disabled_legacy_path"


def test_routed_provider_error_is_invariant_safety_net(monkeypatch):
    """RoutedProviderError is defense-in-depth — decide_route already
    reroutes a blocked expensive provider, so it must not fire on the
    normal blocked path."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "offline-test-key")
    try:
        resolve_routed_provider("planning", provider_override="kimi")
    except RoutedProviderError:
        pytest.fail("blocked kimi must reroute, not raise")


def test_planning_route_no_kimi_bypass(monkeypatch):
    """End-to-end: a kimi override on the planning route does not execute
    Kimi (it reroutes to the keyless hosted provider and 400s)."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(config, "KIMI_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "KIMI_AUTO_FALLBACK_ENABLED", False)
    proj = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    ticket = client.post(
        "/tickets",
        json={"title": "t", "description": "d", "project_id": proj["id"]},
    ).json()
    res = client.post(
        f"/tickets/{ticket['id']}/planning-runs", json={"provider": "kimi"}
    )
    assert res.status_code == 400


def test_planning_route_uses_mock_default_end_to_end():
    proj = client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()
    ticket = client.post(
        "/tickets",
        json={"title": "t", "description": "d", "project_id": proj["id"]},
    ).json()
    res = client.post(f"/tickets/{ticket['id']}/planning-runs")
    assert res.status_code == 201
    assert res.json()["agent_run"]["provider"] == "mock"
