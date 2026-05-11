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
}

INCIDENT_PAYLOAD = {
    "title": "Production API latency spike",
    "description": "Users report increased latency on checkout API.",
    "severity": "sev3",
    "source": "manual",
    "environment": "production",
    "affected_area": "checkout-api",
    "evidence": "p99 latency rose from 200ms to 1800ms over 10m.",
}


def _create_project(name: str = "IncProj") -> dict:
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


def _create_pr_draft(project_id: str, repo_id: str, dev_task_id: str) -> dict:
    resp = client.post(
        f"/projects/{project_id}/pr-drafts",
        json={"code_repository_id": repo_id, "dev_task_id": dev_task_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_ci_event(project_id: str) -> dict:
    resp = client.post(f"/projects/{project_id}/ci-events", json=CI_EVENT_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

def test_record_incident_returns_201_with_shape():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/incidents",
        json=INCIDENT_PAYLOAD,
    )
    assert resp.status_code == 201, resp.text
    inc = resp.json()
    assert inc["id"]
    assert inc["project_id"] == project["id"]
    assert inc["title"] == INCIDENT_PAYLOAD["title"]
    assert inc["description"] == INCIDENT_PAYLOAD["description"]
    assert inc["severity"] == "sev3"
    assert inc["status"] == "reported"
    assert inc["source"] == "manual"
    assert inc["environment"] == "production"
    assert inc["affected_area"] == "checkout-api"
    assert inc["evidence"].startswith("p99 latency rose")
    assert inc["resolved_at"] is None
    assert inc["created_at"]
    assert inc["updated_at"]


def test_record_incident_with_all_links():
    project, task = _create_dev_task()
    repo = _create_repo(project["id"])
    draft = _create_pr_draft(project["id"], repo["id"], task["id"])
    event = _create_ci_event(project["id"])
    subtasks = client.get(f"/dev-tasks/{task['id']}/subtasks").json()
    subtask_id = subtasks[0]["id"] if subtasks else None

    body = {
        **INCIDENT_PAYLOAD,
        "code_repository_id": repo["id"],
        "ci_event_id": event["id"],
        "pr_draft_id": draft["id"],
        "dev_task_id": task["id"],
    }
    if subtask_id:
        body["subtask_id"] = subtask_id

    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 201, resp.text
    inc = resp.json()
    assert inc["code_repository_id"] == repo["id"]
    assert inc["ci_event_id"] == event["id"]
    assert inc["pr_draft_id"] == draft["id"]
    assert inc["dev_task_id"] == task["id"]
    if subtask_id:
        assert inc["subtask_id"] == subtask_id


def test_record_incident_missing_project_returns_404():
    resp = client.post("/projects/does-not-exist/incidents", json=INCIDENT_PAYLOAD)
    assert resp.status_code == 404


def test_record_incident_missing_code_repository_returns_404():
    project = _create_project()
    body = {**INCIDENT_PAYLOAD, "code_repository_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 404


def test_record_incident_missing_ci_event_returns_404():
    project = _create_project()
    body = {**INCIDENT_PAYLOAD, "ci_event_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 404


def test_record_incident_missing_pr_draft_returns_404():
    project = _create_project()
    body = {**INCIDENT_PAYLOAD, "pr_draft_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 404


def test_record_incident_missing_dev_task_returns_404():
    project = _create_project()
    body = {**INCIDENT_PAYLOAD, "dev_task_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 404


def test_record_incident_missing_subtask_returns_404():
    project = _create_project()
    body = {**INCIDENT_PAYLOAD, "subtask_id": "missing"}
    resp = client.post(f"/projects/{project['id']}/incidents", json=body)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_project_incidents_returns_only_project_incidents():
    project_a = _create_project("A")
    project_b = _create_project("B")
    client.post(f"/projects/{project_a['id']}/incidents", json=INCIDENT_PAYLOAD)
    client.post(f"/projects/{project_a['id']}/incidents", json=INCIDENT_PAYLOAD)
    client.post(f"/projects/{project_b['id']}/incidents", json=INCIDENT_PAYLOAD)

    resp = client.get(f"/projects/{project_a['id']}/incidents")
    assert resp.status_code == 200
    incs = resp.json()
    assert len(incs) == 2
    assert all(i["project_id"] == project_a["id"] for i in incs)


def test_list_project_incidents_missing_project_returns_404():
    resp = client.get("/projects/missing/incidents")
    assert resp.status_code == 404


def test_get_incident_returns_one_and_404_on_missing():
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()

    ok = client.get(f"/incidents/{created['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == created["id"]

    miss = client.get("/incidents/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_patch_incident_updates_whitelisted_fields():
    project = _create_project()
    inc = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()

    resp = client.patch(
        f"/incidents/{inc['id']}",
        json={
            "status": "triaging",
            "severity": "sev2",
            "affected_area": "checkout-api/cart",
            "evidence": "Updated evidence with new logs.",
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["status"] == "triaging"
    assert updated["severity"] == "sev2"
    assert updated["affected_area"] == "checkout-api/cart"
    assert updated["evidence"] == "Updated evidence with new logs."
    # Untouched fields preserved
    assert updated["title"] == INCIDENT_PAYLOAD["title"]
    assert updated["updated_at"] >= inc["updated_at"]


def test_patch_incident_missing_returns_404():
    resp = client.patch("/incidents/missing", json={"status": "resolved"})
    assert resp.status_code == 404


def test_patch_incident_writes_audit_event():
    project = _create_project()
    inc = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    client.patch(f"/incidents/{inc['id']}", json={"status": "triaging"})

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("incident_updated", inc["id"]) in actions


# ---------------------------------------------------------------------------
# Audit events on record
# ---------------------------------------------------------------------------

def test_record_incident_writes_audit_event():
    project = _create_project()
    created = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("incident_recorded", created["id"]) in actions


# ---------------------------------------------------------------------------
# Prepare remediation
# ---------------------------------------------------------------------------

def test_prepare_remediation_returns_draft_and_marks_incident_planned():
    project = _create_project()
    inc = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    # Run an analysis first so the draft has a remediation plan to summarize.
    client.post(f"/incidents/{inc['id']}/analysis", json={})

    resp = client.post(f"/incidents/{inc['id']}/prepare-remediation")
    assert resp.status_code == 201, resp.text
    draft = resp.json()
    assert draft["incident_id"] == inc["id"]
    assert draft["project_id"] == project["id"]
    assert draft["title"].startswith("Remediation:")
    assert draft["requires_human_approval"] is True
    assert draft["analysis_id"]
    assert "Suggested remediation plan" in draft["description"]
    assert draft["suggested_acceptance_criteria"]

    # Incident status moved to remediation_planned.
    refreshed = client.get(f"/incidents/{inc['id']}").json()
    assert refreshed["status"] == "remediation_planned"


def test_prepare_remediation_without_analysis_still_returns_draft():
    project = _create_project()
    inc = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    resp = client.post(f"/incidents/{inc['id']}/prepare-remediation")
    assert resp.status_code == 201, resp.text
    draft = resp.json()
    assert draft["analysis_id"] is None
    assert draft["suggested_acceptance_criteria"] == []


def test_prepare_remediation_missing_incident_returns_404():
    resp = client.post("/incidents/missing/prepare-remediation")
    assert resp.status_code == 404


def test_prepare_remediation_writes_audit_event():
    project = _create_project()
    inc = client.post(
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    ).json()
    client.post(f"/incidents/{inc['id']}/prepare-remediation")
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("remediation_work_item_prepared", inc["id"]) in actions


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_record_incident_does_not_invoke_subprocess_or_network(monkeypatch):
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
        f"/projects/{project['id']}/incidents", json=INCIDENT_PAYLOAD
    )
    assert resp.status_code == 201
    assert called == [], f"Unexpected external calls: {called}"
