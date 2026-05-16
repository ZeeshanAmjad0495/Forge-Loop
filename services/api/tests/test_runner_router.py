"""Task 77: RunnerRouter — OpenHands is not the default; it is
approval-gated and reserved for broad multi-file work. Pure decision;
no real runner is invoked."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services.runner_router import (
    RunnerRoutePreviewRequest,
    decide_runner,
    runner_routing_summary,
)

client = TestClient(app)


# 1. Small single-file task -> lightweight (not OpenHands).
def test_small_task_uses_lightweight():
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="feature", estimated_files=1))
    assert d.runner_name == "lightweight"
    assert d.runner_name != "openhands"


# 2. Docs-only -> lightweight.
def test_docs_only_uses_lightweight():
    d = decide_runner(RunnerRoutePreviewRequest(task_type="docs"))
    assert d.runner_name == "lightweight"
    assert d.task_complexity == "tiny"


# 3. Test-only / check -> deterministic or lightweight (never OpenHands).
def test_test_only_uses_lightweight():
    d = decide_runner(RunnerRoutePreviewRequest(task_type="tests"))
    assert d.runner_name in ("lightweight", "deterministic")
    assert d.runner_name != "openhands"


def test_check_workflow_uses_deterministic():
    d = decide_runner(RunnerRoutePreviewRequest(task_type="qa"))
    assert d.runner_name == "deterministic"


# 4. Multi-file medium/large -> OpenHands ONLY when allowed+approved.
def test_multifile_openhands_only_when_allowed_and_approved():
    base = dict(task_type="feature", multi_file=True, estimated_files=8)
    # not allowed -> not openhands
    d1 = decide_runner(RunnerRoutePreviewRequest(**base))
    assert d1.runner_name != "openhands"
    assert d1.task_complexity == "large"
    # allowed + approved -> openhands
    d2 = decide_runner(RunnerRoutePreviewRequest(
        **base, allow_openhands=True, openhands_approved=True))
    assert d2.runner_name == "openhands"


# 5. OpenHands blocked when require-approval true and approval missing.
def test_openhands_blocked_without_approval(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_REQUIRE_APPROVAL", True)
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="feature", multi_file=True, estimated_files=10,
        allow_openhands=True, openhands_approved=False))
    assert d.runner_name != "openhands"
    assert d.requires_human_approval is True
    assert any("openhands_requires_approval" in w for w in d.warnings)


def test_openhands_allowed_when_auto_select_on(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_AUTO_SELECT_ENABLED", True)
    monkeypatch.setattr(config, "OPENHANDS_REQUIRE_APPROVAL", False)
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="feature", multi_file=True, estimated_files=12))
    assert d.runner_name == "openhands"


# 6. Decision includes reason + fallback + complexity/runtime/risk.
def test_decision_includes_reason_and_fallback():
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="feature", estimated_files=1))
    assert d.reason
    assert d.fallback_runner == "deterministic"  # lightweight -> deterministic
    assert d.estimated_runtime_class in ("tiny", "small", "medium", "large")
    assert d.allowed_commands_profile


# High risk -> approval regardless of runner.
def test_high_risk_requires_approval_any_runner():
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="docs", risk_level="high"))
    assert d.requires_human_approval is True
    assert d.runner_name == "lightweight"  # still cheap; just gated


def test_routing_disabled_uses_default(monkeypatch):
    monkeypatch.setattr(config, "RUNNER_ROUTING_ENABLED", False)
    monkeypatch.setattr(config, "DEFAULT_CODING_RUNNER", "lightweight")
    d = decide_runner(RunnerRoutePreviewRequest(
        task_type="feature", multi_file=True))
    assert d.runner_name == "lightweight"
    assert d.reason == "runner_routing_disabled_use_default"


# Route + audit + summary.
def test_preview_route_and_audit():
    p = client.post(
        "/projects", json={"name": "RR", "description": "d"}
    ).json()
    r = client.post(
        f"/projects/{p['id']}/runner-route/preview",
        json={"task_type": "docs", "source_id": "dt1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["runner_name"] == "lightweight"
    ev = client.get(f"/projects/{p['id']}/audit-events").json()
    assert any(e["action"] == "runner_route_previewed" for e in ev)


def test_runner_routing_summary_endpoint():
    r = client.get("/runtime/runner-routing")
    assert r.status_code == 200
    s = r.json()
    assert s["openhands_require_approval"] is True
    assert s["runner_order"][-1] == "openhands"
