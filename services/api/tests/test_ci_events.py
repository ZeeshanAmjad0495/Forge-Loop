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

CI_EVENT_PAYLOAD = {
    "provider": "github_actions",
    "workflow_name": "Backend CI",
    "job_name": "pytest",
    "branch": "feature/example",
    "status": "completed",
    "conclusion": "failure",
    "failure_summary": "pytest failed",
    "logs_excerpt": "E   AssertionError: expected 200, got 500",
    "raw_payload": {"run_id": "12345"},
}


def _create_project(name: str = "CIProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories", json=REPO_PAYLOAD
    ).json()


def _create_dev_task() -> tuple[dict, dict]:
    project = _create_project()
    req = client.post(
        f"/projects/{project['id']}/requirements", json=REQUIREMENT_PAYLOAD
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return project, decomp["dev_tasks"][0]


def _create_check_run(project_id: str, dev_task_id: str) -> dict:
    return client.post("/check-runs", json={
        "project_id": project_id,
        "target_type": "dev_task",
        "target_id": dev_task_id,
        "status": "completed",
        "conclusion": "failure",
        "summary": "pytest failed",
    }).json()


def _create_pr_draft(project_id: str, repo_id: str, dev_task_id: str) -> dict:
    resp = client.post(
        f"/projects/{project_id}/pr-drafts",
        json={"code_repository_id": repo_id, "dev_task_id": dev_task_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

def test_record_ci_event_returns_201_with_shape():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/ci-events",
        json=CI_EVENT_PAYLOAD,
    )
    assert resp.status_code == 201, resp.text
    e = resp.json()
    assert e["id"]
    assert e["project_id"] == project["id"]
    assert e["provider"] == "github_actions"
    assert e["workflow_name"] == "Backend CI"
    assert e["job_name"] == "pytest"
    assert e["branch"] == "feature/example"
    assert e["status"] == "completed"
    assert e["conclusion"] == "failure"
    assert e["failure_summary"] == "pytest failed"
    assert e["logs_excerpt"].startswith("E   AssertionError")
    assert e["raw_payload"] == {"run_id": "12345"}
    assert e["artifact_id"] is None
    assert e["pr_draft_id"] is None
    assert e["dev_task_id"] is None
    assert e["created_at"]
    assert e["updated_at"]


def test_record_ci_event_with_all_links():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    cr = _create_check_run(project["id"], task["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    subtasks = client.get(f"/dev-tasks/{task['id']}/subtasks").json()
    subtask_id = subtasks[0]["id"] if subtasks else None

    body = {
        **CI_EVENT_PAYLOAD,
        "code_repository_id": repo["id"],
        "pr_draft_id": draft["id"],
        "dev_task_id": task["id"],
        "check_run_id": cr["id"],
    }
    if subtask_id:
        body["subtask_id"] = subtask_id

    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 201, resp.text
    e = resp.json()
    assert e["code_repository_id"] == repo["id"]
    assert e["pr_draft_id"] == draft["id"]
    assert e["dev_task_id"] == task["id"]
    assert e["check_run_id"] == cr["id"]
    if subtask_id:
        assert e["subtask_id"] == subtask_id


def test_record_ci_event_missing_project_returns_404():
    resp = client.post(
        "/projects/does-not-exist/ci-events", json=CI_EVENT_PAYLOAD
    )
    assert resp.status_code == 404


def test_record_ci_event_missing_code_repository_returns_404():
    project = _create_project()
    body = {**CI_EVENT_PAYLOAD, "code_repository_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 404


def test_record_ci_event_missing_pr_draft_returns_404():
    project = _create_project()
    body = {**CI_EVENT_PAYLOAD, "pr_draft_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 404


def test_record_ci_event_missing_dev_task_returns_404():
    project = _create_project()
    body = {**CI_EVENT_PAYLOAD, "dev_task_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 404


def test_record_ci_event_missing_subtask_returns_404():
    project = _create_project()
    body = {**CI_EVENT_PAYLOAD, "subtask_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 404


def test_record_ci_event_missing_check_run_returns_404():
    project = _create_project()
    body = {**CI_EVENT_PAYLOAD, "check_run_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/ci-events", json=body)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_list_project_ci_events_returns_only_project_events():
    project_a = _create_project("A")
    project_b = _create_project("B")
    client.post(f"/projects/{project_a['id']}/ci-events", json=CI_EVENT_PAYLOAD)
    client.post(f"/projects/{project_a['id']}/ci-events", json=CI_EVENT_PAYLOAD)
    client.post(f"/projects/{project_b['id']}/ci-events", json=CI_EVENT_PAYLOAD)

    resp_a = client.get(f"/projects/{project_a['id']}/ci-events")
    assert resp_a.status_code == 200
    events_a = resp_a.json()
    assert len(events_a) == 2
    assert all(e["project_id"] == project_a["id"] for e in events_a)


def test_list_project_ci_events_missing_project_returns_404():
    resp = client.get("/projects/missing/ci-events")
    assert resp.status_code == 404


def test_get_ci_event_returns_event_and_404_on_missing():
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/ci-events", json=CI_EVENT_PAYLOAD
    ).json()
    ok = client.get(f"/ci-events/{created['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == created["id"]

    miss = client.get("/ci-events/nope")
    assert miss.status_code == 404


def test_list_pr_draft_ci_events_filters_correctly():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft_a = _create_pr_draft(project["id"], repo["id"], task["id"])
    draft_b = _create_pr_draft(project["id"], repo["id"], task["id"])

    body_a = {**CI_EVENT_PAYLOAD, "pr_draft_id": draft_a["id"]}
    body_b = {**CI_EVENT_PAYLOAD, "pr_draft_id": draft_b["id"]}
    client.post(f"/projects/{project['id']}/ci-events", json=body_a)
    client.post(f"/projects/{project['id']}/ci-events", json=body_a)
    client.post(f"/projects/{project['id']}/ci-events", json=body_b)

    resp = client.get(f"/pr-drafts/{draft_a['id']}/ci-events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    assert all(e["pr_draft_id"] == draft_a["id"] for e in events)


def test_list_pr_draft_ci_events_missing_draft_returns_404():
    resp = client.get("/pr-drafts/missing/ci-events")
    assert resp.status_code == 404


def test_list_dev_task_ci_events_filters_correctly():
    project, task = _create_dev_task()
    body = {**CI_EVENT_PAYLOAD, "dev_task_id": task["id"]}
    client.post(f"/projects/{project['id']}/ci-events", json=body)
    client.post(f"/projects/{project['id']}/ci-events", json=CI_EVENT_PAYLOAD)

    resp = client.get(f"/dev-tasks/{task['id']}/ci-events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["dev_task_id"] == task["id"]


def test_list_dev_task_ci_events_missing_task_returns_404():
    resp = client.get("/dev-tasks/missing/ci-events")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_record_ci_event_writes_audit_event():
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/ci-events", json=CI_EVENT_PAYLOAD
    ).json()
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("ci_event_recorded", created["id"]) in actions


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_record_ci_event_does_not_invoke_subprocess_or_network(monkeypatch):
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

    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/ci-events", json=CI_EVENT_PAYLOAD
    )
    assert resp.status_code == 201

    assert called == [], f"Unexpected external calls: {called}"
