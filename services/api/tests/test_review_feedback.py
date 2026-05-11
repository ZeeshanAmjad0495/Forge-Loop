"""Tests for Task 39: Review Feedback Loop.

All in-memory. No network, no LLM, no real Firestore, no real OpenHands,
no real git, no real GitHub.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import openhands_execution as _openhands
from app.services import github_client as _github_client
from app.services.openhands_execution import OpenHandsExecutionResult


client = TestClient(app)


REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/octocat/Hello-World",
    "name": "repo",
    "default_branch": "main",
}
REQUIREMENT_PAYLOAD = {
    "title": "Add CSV export",
    "problem_statement": "Users cannot export data.",
}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def block_external_io(monkeypatch):
    """Defense in depth: Task 39 must touch no real I/O. Make every dangerous
    boundary raise on invocation."""

    def fail_urlopen(*a, **kw):
        raise AssertionError("urllib.request.urlopen must not be invoked in Task 39 tests")

    def fail_subprocess(*a, **kw):
        raise AssertionError(f"subprocess.run must not be invoked in Task 39 tests: {a!r}")

    class _BlockingExecutor:
        def run(self, **kw):
            raise AssertionError(
                "OpenHands EXECUTOR must not be invoked in Task 39 tests"
            )

    class _BlockingGitHub:
        def create_draft_pull_request(self, **kw):
            raise AssertionError(
                "GitHub client must not be invoked in Task 39 tests"
            )

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    monkeypatch.setattr(_openhands, "EXECUTOR", _BlockingExecutor())
    monkeypatch.setattr(_github_client, "GITHUB_CLIENT", _BlockingGitHub())


def _create_project(name: str = "P39") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD
    ).json()


def _create_dev_task(project_id: str) -> dict:
    req = client.post(
        f"/projects/{project_id}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return decomp["dev_tasks"][0]


def _create_pr_draft(project_id: str, repo_id: str, dev_task_id: str) -> dict:
    res = client.post(
        f"/projects/{project_id}/pr-drafts",
        json={
            "code_repository_id": repo_id,
            "dev_task_id": dev_task_id,
            "target_branch": "main",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _create_workspace(project_id: str, *, code_repository_id: str | None = None) -> dict:
    body = {
        "name": "ws",
        "workspace_type": "local_created",
        "create_directory": True,
    }
    if code_repository_id:
        body["code_repository_id"] = code_repository_id
    return client.post(f"/projects/{project_id}/workspaces", json=body).json()


def _seed_workspace_branch(project_id, workspace_id, *, name="forgeloop/dev-task/x",
                           code_repository_id=None, dev_task_id=None,
                           status="clean") -> dict:
    """Insert a WorkspaceBranch row directly via the repo."""
    from app.repositories_state import workspace_branch_repo
    from app.models import WorkspaceBranch
    from datetime import datetime, timezone
    import uuid
    now = datetime.now(timezone.utc)
    branch = WorkspaceBranch(
        id=str(uuid.uuid4()),
        project_id=project_id,
        workspace_id=workspace_id,
        code_repository_id=code_repository_id,
        dev_task_id=dev_task_id,
        subtask_id=None,
        tool_run_id=None,
        name=name,
        base_branch="main",
        current_branch=name,
        status=status,
        created_at=now,
        updated_at=now,
        last_inspected_at=now,
        error_message=None,
    )
    workspace_branch_repo.save(branch)
    return branch.model_dump(mode="json")


def _setup_pr_draft() -> dict:
    project = _create_project()
    repo = _create_repo(project["id"])
    task = _create_dev_task(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    return {
        "project_id": project["id"],
        "repo_id": repo["id"],
        "task_id": task["id"],
        "draft_id": draft["id"],
    }


def _create_pr_review_with_findings(draft_id: str, findings: list[dict]) -> dict:
    res = client.post(
        f"/pr-drafts/{draft_id}/reviews",
        json={
            "provider": "kody",
            "mode": "manual",
            "summary": "review",
            "findings": findings,
            "conclusion": "changes_requested",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Manual feedback create / list / get
# ---------------------------------------------------------------------------


def test_create_feedback_returns_201_with_open_status():
    ids = _setup_pr_draft()
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={
            "source": "human",
            "severity": "blocking",
            "category": "tests",
            "summary": "Add missing API tests",
            "details": "The PR does not add regression tests for 401/403.",
            "file_path": "app/api/auth.py",
            "line": 120,
            "recommendation": "Add tests in tests/test_auth.py",
        },
    )
    assert res.status_code == 201, res.text
    fb = res.json()
    assert fb["status"] == "open"
    assert fb["pr_draft_id"] == ids["draft_id"]
    assert fb["project_id"] == ids["project_id"]
    assert fb["severity"] == "blocking"
    assert fb["category"] == "tests"
    assert fb["summary"] == "Add missing API tests"
    assert fb["file_path"] == "app/api/auth.py"
    assert fb["line"] == 120
    # Audit
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "review_feedback_created" for e in events)


def test_create_feedback_404_when_pr_draft_missing():
    res = client.post(
        "/pr-drafts/does-not-exist/feedback-items",
        json={"summary": "x"},
    )
    assert res.status_code == 404


def test_create_feedback_rejects_empty_summary():
    ids = _setup_pr_draft()
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "   "},
    )
    assert res.status_code == 400


def test_create_feedback_rejects_unknown_review_id():
    ids = _setup_pr_draft()
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "x", "pr_review_id": "missing"},
    )
    assert res.status_code == 404


def test_list_feedback_by_pr_draft_newest_first():
    ids = _setup_pr_draft()
    first = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "first"},
    ).json()
    second = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "second"},
    ).json()
    listed = client.get(f"/pr-drafts/{ids['draft_id']}/feedback-items").json()
    assert [f["id"] for f in listed[:2]] == [second["id"], first["id"]]


def test_get_feedback_404_and_200():
    res = client.get("/review-feedback/missing")
    assert res.status_code == 404
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    res = client.get(f"/review-feedback/{fb['id']}")
    assert res.status_code == 200
    assert res.json()["id"] == fb["id"]


# ---------------------------------------------------------------------------
# PATCH feedback (safe fields + status transitions)
# ---------------------------------------------------------------------------


def test_patch_feedback_updates_safe_fields():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "x", "severity": "warning", "category": "other"},
    ).json()
    res = client.patch(f"/review-feedback/{fb['id']}", json={
        "severity": "blocking",
        "category": "tests",
        "summary": "Updated summary",
        "details": "Details here",
        "recommendation": "Recommendation here",
    })
    assert res.status_code == 200
    updated = res.json()
    assert updated["severity"] == "blocking"
    assert updated["category"] == "tests"
    assert updated["summary"] == "Updated summary"
    assert updated["details"] == "Details here"
    assert updated["recommendation"] == "Recommendation here"
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "review_feedback_updated" for e in events)


def test_patch_feedback_rejects_invalid_status_transition():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    # open -> in_progress is disallowed (must go through accepted/revision_planned)
    res = client.patch(f"/review-feedback/{fb['id']}", json={"status": "in_progress"})
    assert res.status_code == 400


@pytest.mark.parametrize("target_status, expected_action", [
    ("accepted", "review_feedback_updated"),
    ("rejected", "review_feedback_rejected"),
    ("deferred", "review_feedback_deferred"),
])
def test_patch_feedback_status_audit_action(target_status, expected_action):
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    res = client.patch(f"/review-feedback/{fb['id']}", json={"status": target_status})
    assert res.status_code == 200
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == expected_action for e in events)


def test_patch_feedback_terminal_rejects():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    client.patch(f"/review-feedback/{fb['id']}", json={"status": "rejected"})
    # Cannot modify after rejected.
    res = client.patch(f"/review-feedback/{fb['id']}", json={"summary": "x2"})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Import from findings
# ---------------------------------------------------------------------------


def test_import_from_findings_creates_one_per_finding():
    ids = _setup_pr_draft()
    findings = [
        {"severity": "blocking", "category": "security", "message": "Hardcoded secret",
         "file_path": "app/config.py", "line": 7, "recommendation": "Move to env"},
        {"severity": "warning", "category": "tests", "message": "Missing test"},
    ]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)

    res = client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert len(body["feedback_items"]) == 2
    sources = {f["source"] for f in body["feedback_items"]}
    assert sources == {"kody"}
    statuses = {f["status"] for f in body["feedback_items"]}
    assert statuses == {"open"}
    # Audit + artifact
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "review_feedback_imported" for e in events)


def test_import_from_findings_is_idempotent():
    ids = _setup_pr_draft()
    findings = [
        {"severity": "blocking", "category": "security", "message": "Hardcoded secret",
         "file_path": "app/config.py", "line": 7},
    ]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)
    first = client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings").json()
    second = client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings").json()
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] == 1
    listed = client.get(f"/pr-drafts/{ids['draft_id']}/feedback-items").json()
    assert len(listed) == 1


def test_import_from_findings_404_when_review_missing():
    res = client.post("/pr-reviews/missing/feedback-items/from-findings")
    assert res.status_code == 404


def test_import_from_findings_with_empty_findings_returns_zero():
    ids = _setup_pr_draft()
    review = _create_pr_review_with_findings(ids["draft_id"], [])
    res = client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings")
    assert res.status_code == 201
    body = res.json()
    assert body["created"] == 0
    assert body["skipped"] == 0


def test_import_from_findings_writes_audit_once():
    ids = _setup_pr_draft()
    findings = [{"severity": "warning", "category": "tests", "message": "x"}]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)
    client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings")
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    imported = [e for e in events if e["action"] == "review_feedback_imported"]
    assert len(imported) == 1


def test_import_from_findings_skips_empty_messages():
    ids = _setup_pr_draft()
    findings = [
        {"severity": "warning", "category": "tests", "message": ""},
        {"severity": "warning", "category": "tests", "message": "real"},
    ]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)
    body = client.post(
        f"/pr-reviews/{review['id']}/feedback-items/from-findings"
    ).json()
    assert body["created"] == 1
    assert body["skipped"] == 1


# ---------------------------------------------------------------------------
# Plan revision
# ---------------------------------------------------------------------------


def test_plan_revision_creates_work_item_and_updates_feedback():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "Address tests", "severity": "blocking", "category": "tests"},
    ).json()
    ws = _create_workspace(ids["project_id"], code_repository_id=ids["repo_id"])

    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws["id"]},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    rwi = body["revision_work_item"]
    assert rwi["status"] == "proposed"
    assert rwi["pr_draft_id"] == ids["draft_id"]
    assert rwi["review_feedback_id"] == fb["id"]
    assert rwi["workspace_id"] == ws["id"]
    assert rwi["requires_approval"] is True
    assert rwi["title"].startswith("Revision: address feedback")
    assert "Severity" in rwi["description"]

    fb_after = body["review_feedback"]
    assert fb_after["status"] == "revision_planned"
    assert fb_after["revision_work_item_id"] == rwi["id"]

    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "revision_work_item_planned" for e in events)


def test_plan_revision_404_when_feedback_missing():
    res = client.post(
        "/review-feedback/missing/plan-revision",
        json={"workspace_id": "x"},
    )
    assert res.status_code == 404


def test_plan_revision_404_when_workspace_missing():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": "missing"},
    )
    assert res.status_code == 404


def test_plan_revision_400_workspace_project_mismatch():
    ids_a = _setup_pr_draft()
    project_b = _create_project("Other")
    ws_b = _create_workspace(project_b["id"])
    fb = client.post(
        f"/pr-drafts/{ids_a['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws_b["id"]},
    )
    assert res.status_code == 400


def test_plan_revision_rejects_resolved_feedback():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    client.post(
        f"/review-feedback/{fb['id']}/resolve",
        json={"resolution_summary": "fixed"},
    )
    ws = _create_workspace(ids["project_id"])
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws["id"]},
    )
    assert res.status_code == 400


def test_plan_revision_validates_branch_linkage():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    ws = _create_workspace(ids["project_id"], code_repository_id=ids["repo_id"])
    other_ws = _create_workspace(ids["project_id"])
    branch_other_ws = _seed_workspace_branch(
        ids["project_id"], other_ws["id"], name="forgeloop/dev-task/abc"
    )
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={
            "workspace_id": ws["id"],
            "workspace_branch_id": branch_other_ws["id"],
        },
    )
    assert res.status_code == 400


def test_plan_revision_rejects_failed_branch():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    ws = _create_workspace(ids["project_id"], code_repository_id=ids["repo_id"])
    branch = _seed_workspace_branch(
        ids["project_id"], ws["id"],
        name="forgeloop/dev-task/zz",
        code_repository_id=ids["repo_id"],
        status="failed",
    )
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws["id"], "workspace_branch_id": branch["id"]},
    )
    assert res.status_code == 400


def test_plan_revision_does_not_invoke_openhands_or_git_or_github():
    """The block_external_io autouse fixture makes any external call fail; if
    this test passes, the plan flow truly does not touch those boundaries."""
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    ws = _create_workspace(ids["project_id"], code_repository_id=ids["repo_id"])
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws["id"]},
    )
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# RevisionWorkItem PATCH + approval gate
# ---------------------------------------------------------------------------


def _plan_revision(ids: dict, *, approval_required: bool = True) -> dict:
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    ws = _create_workspace(ids["project_id"], code_repository_id=ids["repo_id"])
    res = client.post(
        f"/review-feedback/{fb['id']}/plan-revision",
        json={"workspace_id": ws["id"], "approval_required": approval_required},
    )
    assert res.status_code == 201, res.text
    return res.json()["revision_work_item"]


def _approve(project_id: str, target_type: str, target_id: str) -> dict:
    created = client.post("/approvals", json={
        "project_id": project_id,
        "target_type": target_type,
        "target_id": target_id,
    }).json()
    decided = client.patch(
        f"/approvals/{created['id']}", json={"status": "approved"}
    ).json()
    return decided


def test_patch_revision_status_to_approved_requires_approval_row():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    res = client.patch(
        f"/revision-work-items/{rwi['id']}",
        json={"status": "approved"},
    )
    assert res.status_code == 400
    assert "approval required" in res.text.lower()


def test_patch_revision_status_to_approved_with_approval_succeeds():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    _approve(ids["project_id"], "revision_work_item", rwi["id"])
    res = client.patch(
        f"/revision-work-items/{rwi['id']}",
        json={"status": "approved"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved"
    assert body["approved_at"] is not None


def test_patch_revision_skip_approval_when_not_required():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids, approval_required=False)
    res = client.patch(
        f"/revision-work-items/{rwi['id']}",
        json={"status": "approved"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


def test_patch_revision_disallows_invalid_status_transition():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    # proposed -> in_progress is not allowed (must pass through approved).
    res = client.patch(
        f"/revision-work-items/{rwi['id']}",
        json={"status": "in_progress"},
    )
    assert res.status_code == 400


def test_patch_revision_terminal_rejects():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    client.patch(f"/revision-work-items/{rwi['id']}", json={"status": "rejected"})
    res = client.patch(
        f"/revision-work-items/{rwi['id']}",
        json={"title": "after rejected"},
    )
    assert res.status_code == 400


def test_list_revision_work_items_for_draft():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    listed = client.get(
        f"/pr-drafts/{ids['draft_id']}/revision-work-items"
    ).json()
    assert any(r["id"] == rwi["id"] for r in listed)


def test_get_revision_work_item_200_and_404():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    assert client.get(f"/revision-work-items/{rwi['id']}").status_code == 200
    assert client.get("/revision-work-items/missing").status_code == 404


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def test_resolve_feedback_marks_resolved_and_updates_linked_revision():
    ids = _setup_pr_draft()
    rwi = _plan_revision(ids)
    # Approve + transition to a non-terminal status.
    _approve(ids["project_id"], "revision_work_item", rwi["id"])
    client.patch(f"/revision-work-items/{rwi['id']}", json={"status": "approved"})
    client.patch(f"/revision-work-items/{rwi['id']}", json={"status": "in_progress"})

    feedback_id = client.get(f"/revision-work-items/{rwi['id']}").json()["review_feedback_id"]
    res = client.post(
        f"/review-feedback/{feedback_id}/resolve",
        json={"resolution_summary": "Added regression tests."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved"
    assert body["resolution_summary"] == "Added regression tests."
    assert body["resolved_at"] is not None

    rwi_after = client.get(f"/revision-work-items/{rwi['id']}").json()
    assert rwi_after["status"] == "resolved"
    assert rwi_after["resolved_at"] is not None

    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "review_feedback_resolved" for e in events)


def test_cannot_resolve_already_resolved_feedback():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    client.post(
        f"/review-feedback/{fb['id']}/resolve",
        json={"resolution_summary": "ok"},
    )
    res = client.post(
        f"/review-feedback/{fb['id']}/resolve",
        json={"resolution_summary": "again"},
    )
    assert res.status_code == 400


def test_resolve_rejects_empty_resolution_summary():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    res = client.post(
        f"/review-feedback/{fb['id']}/resolve",
        json={"resolution_summary": "  "},
    )
    assert res.status_code == 400


def test_resolve_does_not_modify_pr_draft_or_review_state():
    ids = _setup_pr_draft()
    findings = [{"severity": "blocking", "category": "tests", "message": "x"}]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)
    imported = client.post(
        f"/pr-reviews/{review['id']}/feedback-items/from-findings"
    ).json()
    feedback_id = imported["feedback_items"][0]["id"]

    draft_before = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    review_before = client.get(f"/pr-reviews/{review['id']}").json()

    client.post(
        f"/review-feedback/{feedback_id}/resolve",
        json={"resolution_summary": "fixed"},
    )

    draft_after = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    review_after = client.get(f"/pr-reviews/{review['id']}").json()

    assert draft_before["status"] == draft_after["status"]
    assert draft_before["provider"] == draft_after["provider"]
    assert draft_before.get("external_pr_url") == draft_after.get("external_pr_url")
    assert review_before["status"] == review_after["status"]
    assert review_before["conclusion"] == review_after["conclusion"]


def test_blocking_feedback_does_not_auto_approve_pr():
    ids = _setup_pr_draft()
    draft_before = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items",
        json={"summary": "x", "severity": "blocking", "category": "security"},
    )
    draft_after = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    assert draft_before["status"] == draft_after["status"]
    assert draft_after["status"] != "approved_for_creation"


# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------


def test_resolve_persists_resolution_artifact():
    ids = _setup_pr_draft()
    fb = client.post(
        f"/pr-drafts/{ids['draft_id']}/feedback-items", json={"summary": "x"}
    ).json()
    client.post(
        f"/review-feedback/{fb['id']}/resolve",
        json={"resolution_summary": "fixed it"},
    )
    from app.main import artifact_repo
    artifacts = list(getattr(artifact_repo, "_store", {}).values())
    resolutions = [a for a in artifacts if a.artifact_type == "review_feedback_resolution_summary"]
    assert resolutions
    assert any(json.loads(a.content)["feedback_id"] == fb["id"] for a in resolutions)


def test_import_persists_import_summary_artifact():
    ids = _setup_pr_draft()
    findings = [{"severity": "warning", "category": "tests", "message": "msg"}]
    review = _create_pr_review_with_findings(ids["draft_id"], findings)
    client.post(f"/pr-reviews/{review['id']}/feedback-items/from-findings")
    from app.main import artifact_repo
    artifacts = list(getattr(artifact_repo, "_store", {}).values())
    summaries = [a for a in artifacts if a.artifact_type == "review_feedback_import_summary"]
    assert summaries


def test_plan_persists_revision_plan_artifact():
    ids = _setup_pr_draft()
    _plan_revision(ids)
    from app.main import artifact_repo
    artifacts = list(getattr(artifact_repo, "_store", {}).values())
    plans = [a for a in artifacts if a.artifact_type == "revision_plan_summary"]
    assert plans
