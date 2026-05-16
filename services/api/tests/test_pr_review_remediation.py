"""(c) Review-findings revision loop — review -> approval-gated remediation
work item that re-enters the pipeline. Reuses review_feedback +
revision_work_items services (no parallel system)."""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import WorkspaceBranch
from app.repositories_state import (
    revision_work_item_repo,
    workspace_branch_repo,
)

client = TestClient(app)

REPO = {"provider": "github", "repo_url": "https://github.com/o/r",
        "name": "r", "default_branch": "main"}
REQ = {"title": "t", "problem_statement": "p"}
BLOCKING = [{
    "severity": "blocking", "category": "correctness",
    "message": "unvalidated interval crashes startup",
    "file_path": "scheduler.py", "line": 10,
    "recommendation": "validate SCHEDULER_INTERVAL_SECONDS",
}]


def _chain(conclusion="changes_requested", findings=BLOCKING):
    p = client.post("/projects", json={"name": "RM", "description": "d"}).json()
    repo = client.post(
        f"/projects/{p['id']}/code-repositories", json=REPO
    ).json()
    req = client.post(f"/projects/{p['id']}/requirements", json=REQ).json()
    dt = client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()["dev_tasks"][0]
    draft = client.post(
        f"/projects/{p['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": dt["id"]},
    ).json()
    ws = client.post(
        f"/projects/{p['id']}/workspaces",
        json={"name": "ws", "workspace_type": "local_created",
              "create_directory": True},
    ).json()
    now = datetime.now(timezone.utc)
    br = WorkspaceBranch(
        id=str(uuid.uuid4()), project_id=p["id"], workspace_id=ws["id"],
        code_repository_id=repo["id"], dev_task_id=dt["id"], subtask_id=None,
        tool_run_id=None, name="forgeloop/dev-task/x", base_branch="main",
        current_branch="forgeloop/dev-task/x", status="clean",
        created_at=now, updated_at=now, last_inspected_at=now,
        error_message=None,
    )
    workspace_branch_repo.save(br)
    review = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "manual", "summary": "rv",
              "findings": findings, "conclusion": conclusion},
    ).json()
    return {"project_id": p["id"], "draft_id": draft["id"],
            "review_id": review["id"], "ws_id": ws["id"], "branch_id": br.id}


def test_remediate_creates_approval_gated_revision_work_item():
    c = _chain()
    r = client.post(
        f"/pr-reviews/{c['review_id']}/remediate",
        json={"workspace_id": c["ws_id"],
              "workspace_branch_id": c["branch_id"]},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["revision_work_item_id"]
    assert d["requires_approval"] is True
    assert d["revision_work_item_status"] == "proposed"
    assert d["imported_feedback_ids"]
    # The work item exists, is proposed (NOT auto-executed), bound to branch.
    item = revision_work_item_repo.get(d["revision_work_item_id"])
    assert item is not None
    assert item.status == "proposed"
    assert item.requires_approval is True
    assert item.workspace_branch_id == c["branch_id"]
    # audit recorded
    ev = client.get(f"/projects/{c['project_id']}/audit-events").json()
    assert any(e["action"] == "pr_review_remediation_planned" for e in ev)


def test_remediate_rejects_non_completed_review():
    # A 'prepare' review is pending, not completed.
    p = client.post("/projects", json={"name": "RM2", "description": "d"}).json()
    repo = client.post(
        f"/projects/{p['id']}/code-repositories", json=REPO
    ).json()
    req = client.post(f"/projects/{p['id']}/requirements", json=REQ).json()
    dt = client.post(
        f"/requirements/{req['id']}/task-decompositions"
    ).json()["dev_tasks"][0]
    draft = client.post(
        f"/projects/{p['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": dt["id"]},
    ).json()
    review = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    r = client.post(f"/pr-reviews/{review['id']}/remediate",
                    json={"workspace_id": "x"})
    assert r.status_code == 400
    assert "not 'completed'" in r.text


def test_remediate_rejects_no_actionable_findings():
    c = _chain(conclusion="approved", findings=[])
    r = client.post(f"/pr-reviews/{c['review_id']}/remediate",
                    json={"workspace_id": c["ws_id"]})
    assert r.status_code == 400
    assert "no actionable findings" in r.text


def test_remediate_requires_a_workspace():
    c = _chain()  # draft created without workspace binding
    r = client.post(f"/pr-reviews/{c['review_id']}/remediate", json={})
    assert r.status_code == 400
    assert "no associated workspace" in r.text


def test_remediate_is_idempotent_on_reinvoke():
    c = _chain()
    body = {"workspace_id": c["ws_id"], "workspace_branch_id": c["branch_id"]}
    r1 = client.post(f"/pr-reviews/{c['review_id']}/remediate", json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post(f"/pr-reviews/{c['review_id']}/remediate", json=body)
    # Second call must not 500; still yields a plan from existing feedback.
    assert r2.status_code == 201, r2.text
    assert r2.json()["imported_feedback_ids"]
