import os
import subprocess
import urllib.request

import pytest
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
    "blocked_paths": [".env"],
    "required_checks": ["tests"],
    "requires_approval_for": ["create_pr"],
    "protected_branches": ["main"],
    "notes": "",
}


def _create_project(name: str = "PRProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD
    ).json()


def _create_dev_task(project_id: str | None = None) -> tuple[dict, dict]:
    project = _create_project() if project_id is None else {"id": project_id}
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return project, decomp["dev_tasks"][0]


def _create_tool_run(project_id: str, dev_task_id: str) -> dict:
    return client.post("/tool-runs", json={
        "project_id": project_id,
        "target_type": "dev_task",
        "target_id": dev_task_id,
        "runner_type": "openhands",
        "mode": "dry_run",
        "status": "completed",
        "conclusion": "requires_human_action",
        "summary": "OpenHands instruction package prepared",
        "output": '{"runner":"openhands","mode":"dry_run"}',
    }).json()


def _create_check_run(project_id: str, dev_task_id: str, conclusion: str = "success") -> dict:
    return client.post("/check-runs", json={
        "project_id": project_id,
        "target_type": "dev_task",
        "target_id": dev_task_id,
        "status": "completed",
        "conclusion": conclusion,
        "summary": "pytest passed" if conclusion == "success" else "pytest failed",
    }).json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_prepare_pr_draft_for_dev_task_returns_201_and_shape():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    )
    assert resp.status_code == 201
    d = resp.json()
    assert d["project_id"] == project["id"]
    assert d["code_repository_id"] == repo["id"]
    assert d["dev_task_id"] == task["id"]
    assert d["subtask_id"] is None
    assert d["tool_run_id"] is None
    assert d["status"] == "draft_prepared"
    assert d["provider"] == "manual"
    assert d["target_branch"] == "main"
    assert d["source_branch"].startswith("forgeloop/dev-task/")
    assert d["title"].startswith("[ForgeLoop]")
    assert "## Summary" in d["body"]
    assert d["external_pr_url"] is None
    assert d["approved_at"] is None


def test_prepare_pr_draft_generates_title_and_body_when_unspecified():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    assert task["title"] in d["title"]
    assert "## Linked ForgeLoop items" in d["body"]
    assert "## Human approval checklist" in d["body"]


def test_prepare_pr_draft_uses_supplied_title_and_body():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": repo["id"],
            "dev_task_id": task["id"],
            "title": "Custom title",
            "body": "Custom body",
        },
    ).json()
    assert d["title"] == "Custom title"
    assert d["body"] == "Custom body"


def test_prepare_pr_draft_includes_tool_run_summary_when_tool_run_id_given():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    run = _create_tool_run(project["id"], task["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": repo["id"],
            "dev_task_id": task["id"],
            "tool_run_id": run["id"],
        },
    ).json()
    assert d["tool_run_id"] == run["id"]
    assert "OpenHands instruction package prepared" in d["body"]
    # Output preview must appear in body
    assert "openhands" in d["body"]


def test_prepare_pr_draft_does_not_claim_tests_passed_without_check_runs():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    body = d["body"]
    assert "No deterministic check runs recorded" in body
    assert "Tests passed" not in body
    assert "QA passed" not in body


def test_prepare_pr_draft_marks_check_runs_when_present():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    _create_check_run(project["id"], task["id"], conclusion="success")
    _create_check_run(project["id"], task["id"], conclusion="failure")
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    body = d["body"]
    assert "[success]" in body
    assert "[failure]" in body
    assert "Not all checks succeeded" in body
    assert "Tests passed" not in body


def test_prepare_pr_draft_for_subtask_only_works():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    subtasks = client.get(f"/dev-tasks/{task['id']}/subtasks").json()
    if not subtasks:
        pytest.skip("No subtasks generated by mock")
    subtask = subtasks[0]
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "subtask_id": subtask["id"]},
    )
    assert resp.status_code == 201
    d = resp.json()
    assert d["dev_task_id"] is None
    assert d["subtask_id"] == subtask["id"]
    assert d["source_branch"].startswith("forgeloop/subtask/")


def test_prepare_pr_draft_missing_project_returns_404():
    resp = client.post(
        "/projects/nonexistent/pr-drafts",
        json={"code_repository_id": "x", "dev_task_id": "y"},
    )
    assert resp.status_code == 404


def test_prepare_pr_draft_missing_repo_returns_404():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": "nonexistent", "dev_task_id": "x"},
    )
    assert resp.status_code == 404


def test_prepare_pr_draft_missing_dev_task_returns_404():
    project = _create_project()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": "nonexistent"},
    )
    assert resp.status_code == 404


def test_prepare_pr_draft_missing_subtask_returns_404():
    project = _create_project()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "subtask_id": "nonexistent"},
    )
    assert resp.status_code == 404


def test_prepare_pr_draft_missing_tool_run_returns_404():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": repo["id"],
            "dev_task_id": task["id"],
            "tool_run_id": "nonexistent",
        },
    )
    assert resp.status_code == 404


def test_prepare_pr_draft_requires_dev_task_or_subtask():
    project = _create_project()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"]},
    )
    assert resp.status_code == 400


def test_prepare_pr_draft_accepts_github_provider():
    """B12: provider='github' is the natural value an end-user reaches for when
    the intent is GitHub publication. Accept it on create — the publication
    step (POST /pr-drafts/{id}/create-github-draft) is still the actual gate
    for pushing to GitHub. Rejecting it here forced users to send 'local' as
    a workaround, which was non-obvious.
    """
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": repo["id"],
            "dev_task_id": task["id"],
            "provider": "github",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "github"


def test_prepare_pr_draft_rejects_unknown_provider():
    """Sanity: still reject genuinely unknown providers."""
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": repo["id"],
            "dev_task_id": task["id"],
            "provider": "bitbucket",
        },
    )
    # Pydantic literal validation returns 422, route check would return 400.
    assert resp.status_code in (400, 422)


def test_prepare_pr_draft_rejects_repo_from_other_project():
    p1 = _create_project("P1")
    p2 = _create_project("P2")
    repo_p2 = _create_repo(p2["id"])
    _, task_p1 = _create_dev_task(p1["id"])
    resp = client.post(
        f"/projects/{p1['id']}/pr-drafts",
        json={"code_repository_id": repo_p2["id"], "dev_task_id": task_p1["id"]},
    )
    assert resp.status_code == 400


def test_prepare_pr_draft_writes_audit_pr_draft_prepared():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    )
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "pr_draft_prepared" for e in events)


def test_prepare_pr_draft_default_status_is_draft_prepared():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    assert d["status"] == "draft_prepared"


def test_prepare_pr_draft_safety_section_reflects_profile_when_present():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    client.post(f"/code-repositories/{repo['id']}/safety-profile", json=SAFETY_PAYLOAD)
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    body = d["body"]
    assert "work_safe_mode: True" in body
    assert ".env" in body
    assert "Protected branches" in body


def test_prepare_pr_draft_safety_section_warns_when_profile_missing():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    d = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    assert "No repo safety profile configured" in d["body"]


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------

def test_list_project_pr_drafts_filters_by_project():
    p1, t1 = _create_dev_task()
    r1 = _create_repo(p1["id"])
    p2, t2 = _create_dev_task()
    r2 = _create_repo(p2["id"])
    client.post(f"/projects/{p1['id']}/pr-drafts", json={"code_repository_id": r1["id"], "dev_task_id": t1["id"]})
    client.post(f"/projects/{p2['id']}/pr-drafts", json={"code_repository_id": r2["id"], "dev_task_id": t2["id"]})

    items = client.get(f"/projects/{p1['id']}/pr-drafts").json()
    assert len(items) == 1
    assert items[0]["project_id"] == p1["id"]


def test_list_project_pr_drafts_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/pr-drafts")
    assert resp.status_code == 404


def test_get_pr_draft():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    resp = client.get(f"/pr-drafts/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_pr_draft_404():
    resp = client.get("/pr-drafts/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

def test_patch_pr_draft_updates_title_body_and_writes_audit():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    resp = client.patch(
        f"/pr-drafts/{created['id']}",
        json={"title": "New title", "body": "New body"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["title"] == "New title"
    assert d["body"] == "New body"

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    patches = [e for e in events if e["action"] == "pr_draft_updated"]
    assert patches
    assert "title" in patches[0]["details"]["changed_fields"]


def test_patch_pr_draft_allows_external_pr_url_and_number():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    resp = client.patch(
        f"/pr-drafts/{created['id']}",
        json={"external_pr_url": "https://github.com/org/repo/pull/42", "external_pr_number": 42},
    )
    assert resp.status_code == 200
    assert resp.json()["external_pr_url"] == "https://github.com/org/repo/pull/42"
    assert resp.json()["external_pr_number"] == 42


def test_patch_pr_draft_rejects_invalid_status_transition():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    # draft_prepared -> created is not allowed (must go through approve)
    resp = client.patch(f"/pr-drafts/{created['id']}", json={"status": "created"})
    assert resp.status_code == 400


def test_patch_pr_draft_rejects_approved_for_creation_via_patch():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    resp = client.patch(
        f"/pr-drafts/{created['id']}", json={"status": "approved_for_creation"}
    )
    assert resp.status_code == 400


def test_patch_pr_draft_404():
    resp = client.patch("/pr-drafts/nonexistent", json={"title": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def test_approve_pr_draft_marks_approved_for_creation():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    resp = client.post(f"/pr-drafts/{created['id']}/approve")
    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "approved_for_creation"
    assert d["approved_at"] is not None


def test_approve_pr_draft_rejects_when_already_approved():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    client.post(f"/pr-drafts/{created['id']}/approve")
    resp = client.post(f"/pr-drafts/{created['id']}/approve")
    assert resp.status_code == 400


def test_approve_pr_draft_writes_audit_pr_draft_approved():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    created = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    ).json()
    client.post(f"/pr-drafts/{created['id']}/approve")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "pr_draft_approved" for e in events)


def test_approve_pr_draft_404():
    resp = client.post("/pr-drafts/nonexistent/approve")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# No execution / no network
# ---------------------------------------------------------------------------

def test_prepare_pr_draft_does_not_invoke_subprocess_or_network(monkeypatch):
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
    resp = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={"code_repository_id": repo["id"], "dev_task_id": task["id"]},
    )
    assert resp.status_code == 201
    assert called == [], f"Unexpected external calls: {called}"
