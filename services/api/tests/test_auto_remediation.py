"""Task 83: advisory-only auto-remediation tests."""

from datetime import datetime, timezone

import pytest

from app import config
from app.models import (
    Approval,
    CIAnalysis,
    IncidentAnalysis,
    PullRequestReview,
    PullRequestReviewFinding,
)
from app.repositories_state import (
    approval_repo,
    ci_analysis_repo,
    dev_task_repo,
    incident_analysis_repo,
    pr_review_repo,
)


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(config, "AUTO_REMEDIATION_ENABLED", True)


def _project(client):
    return client.post(
        "/projects", json={"name": "P", "description": "d"}
    ).json()["id"]


def _ci(pid, conclusion="code_regression"):
    a = CIAnalysis(
        id="ci-1",
        project_id=pid,
        ci_event_id="evt-1",
        provider="mock",
        model="m",
        status="completed",
        conclusion=conclusion,
        summary="build failed",
        likely_root_causes=["null deref in parser"],
        suggested_fixes=["guard the parser input"],
        affected_areas=["parser"],
        created_at=_now(),
        updated_at=_now(),
    )
    ci_analysis_repo.save(a)
    return a


def _incident(pid):
    a = IncidentAnalysis(
        id="inc-1",
        project_id=pid,
        incident_id="i-1",
        provider="mock",
        model="m",
        status="completed",
        conclusion="security_issue",
        summary="prod 500s",
        likely_root_causes=["bad deploy"],
        remediation_plan=["roll forward fix X"],
        affected_areas=["api"],
        created_at=_now(),
        updated_at=_now(),
    )
    incident_analysis_repo.save(a)
    return a


def _review(pid):
    r = PullRequestReview(
        id="rev-1",
        project_id=pid,
        code_repository_id="cr-1",
        pr_draft_id="pr-1",
        provider="kody",
        status="completed",
        summary="needs work",
        findings=[
            PullRequestReviewFinding(
                severity="blocking", message="SQL injection risk"
            )
        ],
        created_at=_now(),
        updated_at=_now(),
    )
    pr_review_repo.save(r)
    return r


def test_disabled_by_default(client):
    pid = _project(client)
    _ci(pid)
    res = client.post("/ci-analyses/ci-1/propose-remediation")
    assert res.status_code == 409


def test_ci_proposal_created(client, enabled):
    pid = _project(client)
    _ci(pid)
    res = client.post("/ci-analyses/ci-1/propose-remediation")
    assert res.status_code == 201
    body = res.json()
    assert body["source_type"] == "ci_analysis"
    assert body["severity"] == "high"  # code_regression
    assert body["approval_status"] == "pending"
    assert body["suspected_root_cause"]
    assert body["proposed_change"]
    assert body["rollback_note"]
    assert body["tests_to_run"]


def test_incident_proposal_created(client, enabled):
    pid = _project(client)
    _incident(pid)
    res = client.post(
        "/incident-analyses/inc-1/propose-remediation"
    )
    assert res.status_code == 201
    assert res.json()["severity"] == "high"  # security_issue


def test_pr_review_proposal_created(client, enabled):
    pid = _project(client)
    _review(pid)
    res = client.post("/pr-reviews/rev-1/propose-remediation")
    assert res.status_code == 201
    assert res.json()["severity"] == "high"  # blocking finding


def test_approve_without_approval_blocked(client, enabled):
    pid = _project(client)
    _ci(pid)
    pr = client.post("/ci-analyses/ci-1/propose-remediation").json()
    res = client.post(
        f"/remediation-proposals/{pr['id']}/approve"
    )
    assert res.status_code == 400
    # No DevTask created; proposal still pending.
    assert dev_task_repo.list_by_project(pid) == []
    got = client.get(f"/remediation-proposals/{pr['id']}").json()
    assert got["approval_status"] == "pending"
    assert got["dev_task_id"] is None


def test_approved_proposal_creates_dev_task(client, enabled):
    pid = _project(client)
    _ci(pid)
    pr = client.post("/ci-analyses/ci-1/propose-remediation").json()
    now = _now()
    approval_repo.save(
        Approval(
            id="ap-1",
            project_id=pid,
            target_type="remediation_proposal",
            target_id=pr["id"],
            status="approved",
            requested_by="u@example.com",
            created_at=now,
            updated_at=now,
        )
    )
    res = client.post(f"/remediation-proposals/{pr['id']}/approve")
    assert res.status_code == 200
    body = res.json()
    assert body["approval_status"] == "approved"
    assert body["dev_task_id"]
    tasks = dev_task_repo.list_by_project(pid)
    assert len(tasks) == 1
    assert tasks[0].status == "proposed"
    assert tasks[0].priority == "high"
    assert tasks[0].qa_required is True


def test_reject_proposal(client, enabled):
    pid = _project(client)
    _ci(pid)
    pr = client.post("/ci-analyses/ci-1/propose-remediation").json()
    res = client.post(f"/remediation-proposals/{pr['id']}/reject")
    assert res.status_code == 200
    assert res.json()["approval_status"] == "rejected"
    # Cannot approve a rejected proposal.
    assert (
        client.post(
            f"/remediation-proposals/{pr['id']}/approve"
        ).status_code
        == 400
    )


def test_no_auto_merge_or_deploy_surface(client):
    # No auto-merge / auto-deploy config exists.
    assert not any(
        hasattr(config, n)
        for n in (
            "AUTO_REMEDIATION_AUTO_MERGE",
            "AUTO_REMEDIATION_AUTO_DEPLOY",
            "AUTO_REMEDIATION_ENABLE_MERGE",
        )
    )
    assert config.AUTO_REMEDIATION_ALLOW_BRANCH_CREATION is False
    assert config.AUTO_REMEDIATION_ALLOW_PR_CREATION is False
    data = client.get("/runtime/auto-remediation").json()
    assert data["auto_merge"] is False
    assert data["auto_deploy"] is False
    assert data["advisory_only"] is True


def test_advisory_only_forbids_branch_pr(monkeypatch):
    monkeypatch.setattr(config, "AUTO_REMEDIATION_ADVISORY_ONLY", True)
    monkeypatch.setattr(
        config, "AUTO_REMEDIATION_ALLOW_PR_CREATION", True
    )
    monkeypatch.setattr(config, "FORGELOOP_ALLOW_NO_AUTH", True)
    with pytest.raises(RuntimeError, match="ADVISORY_ONLY"):
        config.validate_startup_config()
