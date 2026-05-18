"""Task 90 — RunnerRouter mandatory for real coding execution.

Proves: the router never auto-selects OpenHands for narrow tasks; a
direct OpenHands request the router would route elsewhere is blocked
unless human-approved (then allowed + recorded); Aider stays a valid
lightweight runner; the escape hatch disables enforcement.
"""

from types import SimpleNamespace

import pytest

from app import config
from app.services.runner_router import (
    RunnerRoutePreviewRequest,
    RunnerRouteRejected,
    decide_runner,
    enforce_runner_route,
)


def _task(task_type="unknown", description="do a thing"):
    return SimpleNamespace(
        id="dt-1", task_type=task_type, description=description
    )


def test_decide_runner_narrow_task_avoids_openhands():
    """Unit proof: a narrow task's router decision is never OpenHands."""
    d = decide_runner(
        RunnerRoutePreviewRequest(task_type="documentation", allow_openhands=True)
    )
    assert d.runner_name != "openhands"


def test_narrow_openhands_without_approval_blocked():
    with pytest.raises(RunnerRouteRejected):
        enforce_runner_route(
            _task("documentation"), "openhands", approved=False
        )


def test_narrow_openhands_with_approval_allowed_and_recorded():
    decision = enforce_runner_route(
        _task("documentation"), "openhands", approved=True
    )
    assert decision.runner_name != "openhands"
    assert any(
        w.startswith("runner_router_preferred_")
        and w.endswith("_overridden_by_human_approval")
        for w in decision.warnings
    )


def test_aider_narrow_task_allowed():
    # Aider is a valid lightweight runner — a narrow aider request is
    # not blocked (only a 'deterministic' selection blocks).
    decision = enforce_runner_route(_task("backend"), "aider", approved=True)
    assert decision.runner_name != "openhands"
    assert decision.runner_name != "deterministic"


def test_broad_task_openhands_approved_selected(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_REQUIRE_APPROVAL", True)
    monkeypatch.setattr(config, "OPENHANDS_AUTO_SELECT_ENABLED", False)
    decision = enforce_runner_route(
        _task("refactor", "x" * 50), "openhands", approved=True
    )
    assert decision.runner_name == "openhands"


def test_broad_task_openhands_unapproved_blocked():
    with pytest.raises(RunnerRouteRejected):
        enforce_runner_route(_task("refactor"), "openhands", approved=False)


def test_enforcement_disabled_escape_hatch(monkeypatch):
    monkeypatch.setattr(config, "RUNNER_ROUTER_ENFORCED", False)
    decision = enforce_runner_route(
        _task("documentation"), "openhands", approved=False
    )
    assert "runner_router_enforcement_disabled" in decision.warnings
