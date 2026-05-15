"""Tests for C3: real Kody review execution (submit + poll).

No network — the Kodus client is replaced with a stub. Verifies the
gate, the diff requirement, async-job vs sync paths, poll terminal
mapping, error translation, and team-key redaction.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import kody_review_execution
from app.services.kody_client import KodyAuthError, _redact_key

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}
REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


def _pending_review() -> dict:
    project = client.post(
        "/projects", json={"name": "KodyProj", "description": "d"}
    ).json()
    repo = client.post(
        f"/projects/{project['id']}/code-repositories", json=REPO_PAYLOAD
    ).json()
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    task = client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()["dev_tasks"][0]
    draft = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    review = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    assert review["status"] == "pending"
    return review


class _StubKody:
    def __init__(self, *, start=None, job=None, raise_exc=None):
        self._start = start or {}
        self._job = job or {}
        self._raise = raise_exc
        self.calls: list[tuple] = []

    def start_review(self, **kw):
        self.calls.append(("start", kw))
        if self._raise:
            raise self._raise
        return self._start

    def get_review_job(self, **kw):
        self.calls.append(("poll", kw))
        if self._raise:
            raise self._raise
        return self._job


@pytest.fixture
def kody_enabled(monkeypatch):
    monkeypatch.setattr(config, "KODY_REVIEW_ENABLED", True)
    monkeypatch.setattr(config, "KODY_API_KEY", "kodus_testkey_abc")
    monkeypatch.setattr(config, "KODY_ASYNC", True)


def _patch_client(monkeypatch, stub):
    monkeypatch.setattr(kody_review_execution, "KODY_CLIENT", stub)


# ---------------------------------------------------------------------------


def test_redact_key_scrubs_team_key():
    txt = "auth failed for kodus_secret_value_123 and Bearer kodus_other"
    out = _redact_key(txt, "kodus_secret_value_123")
    assert "kodus_secret_value_123" not in out
    assert "kodus_other" not in out
    assert "***" in out


def test_run_blocked_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "KODY_REVIEW_ENABLED", False)
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run", json={"diff": "x"}
    )
    assert resp.status_code == 409
    assert "KODY_REVIEW_DISABLED" in resp.text


def test_run_blocked_when_key_missing(monkeypatch):
    monkeypatch.setattr(config, "KODY_REVIEW_ENABLED", True)
    monkeypatch.setattr(config, "KODY_API_KEY", "")
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run", json={"diff": "x"}
    )
    assert resp.status_code == 409
    assert "KODY_API_KEY_NOT_CONFIGURED" in resp.text


def test_run_requires_diff(kody_enabled, monkeypatch):
    _patch_client(monkeypatch, _StubKody(start={"jobId": "j1"}))
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run", json={"diff": "   "}
    )
    assert resp.status_code == 400
    assert "diff is required" in resp.text


def test_run_async_sets_running_with_job_id(kody_enabled, monkeypatch):
    stub = _StubKody(start={"jobId": "job-123"})
    _patch_client(monkeypatch, stub)
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run",
        json={"diff": "diff --git a/x b/x\n+1", "branch": "forgeloop/x"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "running"
    assert "job-123" in (data["raw_output"] or "")
    # The team key reached the client (not asserted by value here).
    assert stub.calls[0][0] == "start"
    assert stub.calls[0][1]["diff"].startswith("diff --git")


def test_run_sync_completes_and_maps_severity(kody_enabled, monkeypatch):
    stub = _StubKody(start={
        "summary": "2 issues",
        "issues": [
            {"file": "a.py", "line": 3, "severity": "high",
             "category": "security", "message": "SQLi",
             "recommendation": "use params"},
            {"file": "b.py", "line": 9, "severity": "low",
             "message": "nit"},
        ],
        "filesAnalyzed": 2,
    })
    _patch_client(monkeypatch, stub)
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run",
        json={"diff": "d", "async_mode": False},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["conclusion"] == "changes_requested"  # has a blocking finding
    sev = sorted(f["severity"] for f in data["findings"])
    assert sev == ["blocking", "info"]
    sec = [f for f in data["findings"] if f["category"] == "security"]
    assert sec and sec[0]["file_path"] == "a.py"


def test_run_translates_auth_error(kody_enabled, monkeypatch):
    _patch_client(
        monkeypatch, _StubKody(raise_exc=KodyAuthError("bad key", status=401))
    )
    review = _pending_review()
    resp = client.post(
        f"/pr-reviews/{review['id']}/kody/run", json={"diff": "d"}
    )
    assert resp.status_code == 502
    assert "kody_auth_failed" in resp.text


def test_poll_still_running_returns_unchanged(kody_enabled, monkeypatch):
    _patch_client(monkeypatch, _StubKody(start={"jobId": "j9"}))
    review = _pending_review()
    client.post(
        f"/pr-reviews/{review['id']}/kody/run", json={"diff": "d"}
    )
    _patch_client(monkeypatch, _StubKody(job={"status": "RUNNING"}))
    resp = client.post(f"/pr-reviews/{review['id']}/kody/poll")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "running"


def test_poll_completed_records_findings(kody_enabled, monkeypatch):
    _patch_client(monkeypatch, _StubKody(start={"jobId": "j7"}))
    review = _pending_review()
    client.post(f"/pr-reviews/{review['id']}/kody/run", json={"diff": "d"})

    _patch_client(monkeypatch, _StubKody(job={
        "status": "COMPLETED",
        "result": {
            "summary": "ok",
            "issues": [{"file": "z.py", "line": 1,
                        "severity": "medium", "message": "warn me"}],
        },
    }))
    resp = client.post(f"/pr-reviews/{review['id']}/kody/poll")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["conclusion"] == "comment_only"
    assert data["findings"][0]["severity"] == "warning"


def test_poll_failed_marks_failed(kody_enabled, monkeypatch):
    _patch_client(monkeypatch, _StubKody(start={"jobId": "j5"}))
    review = _pending_review()
    client.post(f"/pr-reviews/{review['id']}/kody/run", json={"diff": "d"})

    _patch_client(monkeypatch, _StubKody(job={
        "status": "FAILED", "error": "sandbox exploded"
    }))
    resp = client.post(f"/pr-reviews/{review['id']}/kody/poll")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "failed"
    assert "sandbox exploded" in (data["error_message"] or "")
