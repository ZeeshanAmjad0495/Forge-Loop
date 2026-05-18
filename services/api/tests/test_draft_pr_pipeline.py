"""Task 100 — end-to-end draft-PR pipeline (orchestration only).

Dormant by default; approval + runner-evidence + passing-check gated;
compounded downstream flags; terminal state at most 'draft_pr_opened'.
Pure fakes — no real git/GitHub/network.
"""

from types import SimpleNamespace

import pytest

from app import config
from app.services import draft_pr_pipeline as dp


class _FakeApprovals:
    def __init__(self, approved):
        self._a = approved

    def find_approved_for_target(self, t, tid, pid):
        return self._a


class _FakeList:
    def __init__(self, items):
        self._i = items

    def list_by_project(self, pid):
        return self._i


def _wire(monkeypatch, *, approval=True, tool_runs=True, passing=True):
    monkeypatch.setattr(
        dp, "dev_task_repo",
        SimpleNamespace(get=lambda i: SimpleNamespace(
            id=i, project_id="p1")),
    )
    monkeypatch.setattr(
        dp, "approval_repo",
        _FakeApprovals(SimpleNamespace(id="ap1") if approval else None),
    )
    tr = [SimpleNamespace(dev_task_id="dt1")] if tool_runs else []
    monkeypatch.setattr(dp, "tool_run_repo", _FakeList(tr))
    cr = (
        [SimpleNamespace(conclusion="success")] if passing
        else [SimpleNamespace(conclusion="failure")]
    )
    monkeypatch.setattr(dp, "check_run_repo", _FakeList(cr))


def test_dormant_by_default(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", False)
    _wire(monkeypatch)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.enabled is False
    assert r.final_status == "disabled"
    assert r.awaiting_human_review is True


def test_blocked_without_approval(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    _wire(monkeypatch, approval=False)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.final_status == "blocked"
    assert r.steps[-1].name == "approval"
    assert r.steps[-1].status == "blocked"


def test_blocked_without_runner_evidence(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    _wire(monkeypatch, tool_runs=False)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.final_status == "blocked"
    assert r.steps[-1].name == "runner_evidence"


def test_blocked_without_passing_check(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    _wire(monkeypatch, passing=False)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.final_status == "blocked"
    assert r.steps[-1].name == "checks"


def test_compounded_flags_push_off_blocks(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_PUSH_ENABLED", False)
    _wire(monkeypatch)
    r = dp.run_pipeline("dt1", "u@x")
    # Approval/runner/checks pass, but push gate off -> blocked.
    assert r.final_status == "blocked"
    assert r.steps[-1].name == "branch_commit"
    assert r.steps[-1].status == "skipped_flag_off"


def test_happy_path_stops_at_draft_pr(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_PUSH_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    _wire(monkeypatch)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.final_status == "draft_pr_opened"
    assert r.awaiting_human_review is True
    names = [s.name for s in r.steps]
    assert names == [
        "approval", "runner_evidence", "checks",
        "branch_commit", "push", "draft_pr",
    ]
    # Hard invariant: never merge / ready / deploy.
    blob = " ".join(s.name + s.detail for s in r.steps).lower()
    for forbidden in ("merge", "ready", "deploy", "force"):
        assert forbidden not in blob


def test_push_on_integration_off_stops_at_pushed(monkeypatch):
    monkeypatch.setattr(config, "DRAFT_PR_PIPELINE_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_PUSH_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", False)
    _wire(monkeypatch)
    r = dp.run_pipeline("dt1", "u@x")
    assert r.final_status == "pushed"
    assert r.steps[-1].name == "draft_pr"
    assert r.steps[-1].status == "skipped_flag_off"
