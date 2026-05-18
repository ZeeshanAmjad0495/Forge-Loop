"""Task 96 — real metrics wiring at the Release-10 chokepoints.

All emission is a no-op unless metrics are enabled (Task 82 design), so
wiring is non-breaking. Labels are enum-like identifiers only — never
prompts/tokens/PII/secrets.
"""

import pytest

from app import config
from app.services import metrics
from app.services.metrics import (
    record_cache_event,
    record_provider_rate_limited,
    record_remediation_proposal,
    record_runner_selected,
    record_workflow_failed,
)


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setattr(config, "OBSERVABILITY_ENABLED", True)
    monkeypatch.setattr(config, "METRICS_ENABLED", True)
    metrics.reset()
    yield
    metrics.reset()


def test_new_signals_increment_and_render():
    record_provider_rate_limited("deepseek")
    record_cache_event(True)
    record_cache_event(False)
    record_cache_event(False)
    record_remediation_proposal("ci_analysis")
    record_runner_selected("lightweight")
    record_workflow_failed("incident_to_triage")
    out = metrics.render()
    assert "provider_rate_limited_total" in out
    assert "cache_hit_total" in out
    assert "cache_miss_total" in out
    assert "remediation_proposal_total" in out
    assert "runner_selected_total" in out
    assert "workflow_failed_total" in out


def test_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(config, "METRICS_ENABLED", False)
    metrics.reset()
    record_provider_rate_limited("kimi")
    record_cache_event(True)
    # render() exposes no series when disabled.
    assert "provider_rate_limited_total{" not in metrics.render()


def test_no_secret_like_labels():
    # Labels must be enum-ish identifiers, never free-form content.
    record_provider_rate_limited("deepseek")
    record_remediation_proposal("incident_analysis")
    out = metrics.render()
    for bad in ("prompt", "api_key", "token=", "secret", "password"):
        assert bad not in out.lower()
