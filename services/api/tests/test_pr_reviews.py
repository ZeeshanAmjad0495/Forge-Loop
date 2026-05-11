import json
import os
import subprocess
import urllib.request

from fastapi.testclient import TestClient

from app.main import app

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

SAFETY_PAYLOAD = {
    "work_safe_mode": True,
    "allowed_actions": ["read_code"],
    "blocked_paths": [".env", "secrets/"],
    "required_checks": ["tests"],
    "requires_approval_for": ["create_pr"],
    "protected_branches": ["main"],
    "notes": "",
}


def _create_project(name: str = "RevProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD
    ).json()


def _put_safety_profile(project_id: str, repo_id: str) -> dict:
    return client.post(
        f"/code-repositories/{repo_id}/safety-profile",
        json=SAFETY_PAYLOAD,
    ).json()


def _create_dev_task(project_id: str | None = None) -> tuple[dict, dict]:
    project = _create_project() if project_id is None else {"id": project_id}
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return project, decomp["dev_tasks"][0]


def _create_check_run(project_id: str, dev_task_id: str, conclusion: str = "success") -> dict:
    return client.post("/check-runs", json={
        "project_id": project_id,
        "target_type": "dev_task",
        "target_id": dev_task_id,
        "status": "completed",
        "conclusion": conclusion,
        "summary": "pytest passed" if conclusion == "success" else "pytest failed",
    }).json()


def _create_pr_draft(project_id: str, repo_id: str, dev_task_id: str) -> dict:
    resp = client.post(
        f"/projects/{project_id}/pr-drafts",
        json={"code_repository_id": repo_id, "dev_task_id": dev_task_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_prepare_pr_review_returns_201_pending_with_package():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )
    assert resp.status_code == 201, resp.text
    r = resp.json()
    assert r["pr_draft_id"] == draft["id"]
    assert r["project_id"] == project["id"]
    assert r["code_repository_id"] == repo["id"]
    assert r["provider"] == "kody"
    assert r["status"] == "pending"
    assert r["conclusion"] is None
    assert r["completed_at"] is None
    assert r["raw_output"]
    package = json.loads(r["raw_output"])
    assert package["provider"] == "kody"
    assert package["mode"] == "prepare"
    assert package["pr_draft"]["title"] == draft["title"]
    assert package["pr_draft"]["body"] == draft["body"]
    assert "review_focus_areas" in package
    assert "correctness" in package["review_focus_areas"]


def test_record_manual_completed_review_on_create():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    findings = [
        {
            "severity": "blocking",
            "category": "security",
            "message": "Hardcoded secret",
            "file_path": "app/config.py",
            "line": 7,
            "recommendation": "Move to env var",
        },
        {"severity": "warning", "category": "tests", "message": "Missing test for X"},
    ]
    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={
            "provider": "kody",
            "mode": "manual",
            "summary": "2 findings: 1 blocking, 1 warning.",
            "findings": findings,
            "recommendations": "Fix blocking before merge.",
            "raw_output": "raw kody output text",
            "conclusion": "changes_requested",
            "external_review_url": "https://kody.example/review/123",
        },
    )
    assert resp.status_code == 201, resp.text
    r = resp.json()
    assert r["status"] == "completed"
    assert r["conclusion"] == "changes_requested"
    assert r["completed_at"] is not None
    assert r["summary"].startswith("2 findings")
    assert len(r["findings"]) == 2
    assert r["findings"][0]["severity"] == "blocking"
    assert r["findings"][0]["category"] == "security"
    assert r["findings"][0]["file_path"] == "app/config.py"
    assert r["external_review_url"] == "https://kody.example/review/123"


def test_create_review_missing_pr_draft_returns_404():
    resp = client.post(
        "/pr-drafts/does-not-exist/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Package content
# ---------------------------------------------------------------------------

def test_review_package_includes_qa_evidence_when_check_runs_exist():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    cr = _create_check_run(project["id"], task["id"], conclusion="success")
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )
    r = resp.json()
    package = json.loads(r["raw_output"])
    qa = package["qa_evidence"]
    assert isinstance(qa, list) and len(qa) == 1
    assert qa[0]["check_run_id"] == cr["id"]
    assert qa[0]["conclusion"] == "success"


def test_review_package_includes_safety_block_when_profile_exists():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    _put_safety_profile(project["id"], repo["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )
    package = json.loads(resp.json()["raw_output"])
    assert package["safety"] is not None
    assert ".env" in package["safety"]["blocked_paths"]
    assert package["safety"]["work_safe_mode"] is True


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_reviews_returns_newest_first_filtered_by_pr_draft():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft_a = _create_pr_draft(project["id"], repo["id"], task["id"])

    # second draft on same task
    draft_b = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()

    r1 = client.post(
        f"/pr-drafts/{draft_a['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    r2 = client.post(
        f"/pr-drafts/{draft_a['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    # noise: belongs to draft_b
    client.post(
        f"/pr-drafts/{draft_b['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )

    resp = client.get(f"/pr-drafts/{draft_a['id']}/reviews")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert ids[0] == r2["id"]
    assert ids[1] == r1["id"]
    assert len(ids) == 2


def test_list_reviews_missing_draft_returns_404():
    resp = client.get("/pr-drafts/missing/reviews")
    assert resp.status_code == 404


def test_get_pr_review_returns_review_and_404_on_missing():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()

    ok = client.get(f"/pr-reviews/{r['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == r["id"]

    miss = client.get("/pr-reviews/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

def test_patch_pr_review_updates_safe_fields():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()

    resp = client.patch(
        f"/pr-reviews/{r['id']}",
        json={
            "summary": "Reviewer notes",
            "findings": [{"severity": "info", "category": "style", "message": "fmt"}],
            "external_review_url": "https://kody.example/r/9",
        },
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["summary"] == "Reviewer notes"
    assert d["findings"][0]["severity"] == "info"
    assert d["external_review_url"] == "https://kody.example/r/9"
    assert d["status"] == "pending"  # unchanged


def test_patch_pr_review_rejects_invalid_status_transition():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    # cancel it
    cancel = client.patch(f"/pr-reviews/{r['id']}", json={"status": "cancelled"})
    assert cancel.status_code == 200
    # cancelled -> running is not allowed
    bad = client.patch(f"/pr-reviews/{r['id']}", json={"status": "running"})
    assert bad.status_code == 400


def test_patch_pr_review_to_completed_requires_conclusion():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    bad = client.patch(f"/pr-reviews/{r['id']}", json={"status": "completed"})
    assert bad.status_code == 400


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------

def test_complete_pr_review_sets_completed_state():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()

    resp = client.post(
        f"/pr-reviews/{r['id']}/complete",
        json={
            "conclusion": "approved",
            "summary": "LGTM",
            "findings": [],
            "recommendations": "ship it",
            "raw_output": "kody output",
        },
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()
    assert d["status"] == "completed"
    assert d["conclusion"] == "approved"
    assert d["completed_at"] is not None
    assert d["summary"] == "LGTM"
    assert d["recommendations"] == "ship it"
    assert d["raw_output"] == "kody output"


def test_complete_pr_review_twice_returns_400():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    client.post(
        f"/pr-reviews/{r['id']}/complete",
        json={"conclusion": "approved"},
    )
    again = client.post(
        f"/pr-reviews/{r['id']}/complete",
        json={"conclusion": "approved"},
    )
    assert again.status_code == 400


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_findings_validation_rejects_unknown_severity():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={
            "provider": "kody",
            "mode": "manual",
            "conclusion": "comment_only",
            "findings": [{"severity": "critical", "message": "bad"}],
        },
    )
    assert resp.status_code == 422


def test_findings_validation_accepts_full_finding():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    resp = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={
            "provider": "kody",
            "mode": "manual",
            "conclusion": "comment_only",
            "findings": [
                {
                    "severity": "warning",
                    "category": "maintainability",
                    "message": "rename var",
                    "file_path": "a.py",
                    "line": 12,
                    "recommendation": "use better name",
                }
            ],
        },
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_audit_events_recorded_for_prepare_and_complete():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    ).json()
    client.post(
        f"/pr-reviews/{r['id']}/complete",
        json={"conclusion": "approved"},
    )

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("pr_review_requested", r["id"]) in actions
    assert ("pr_review_completed", r["id"]) in actions


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_pr_review_flow_does_not_invoke_subprocess_or_network(monkeypatch):
    called: list[tuple] = []

    def fake_run(*args, **kwargs):
        called.append(("subprocess.run", args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    def fake_urlopen(*args, **kwargs):
        called.append(("urlopen", args))
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])

    r = client.post(
        f"/pr-drafts/{draft['id']}/reviews",
        json={"provider": "kody", "mode": "prepare"},
    )
    assert r.status_code == 201
    c = client.post(
        f"/pr-reviews/{r.json()['id']}/complete",
        json={"conclusion": "approved", "summary": "ok"},
    )
    assert c.status_code == 200

    assert called == [], f"Unexpected external calls: {called}"
