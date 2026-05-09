import subprocess
import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_PAYLOAD = {
    "provider": "github",
    "repo_url": "https://github.com/org/repo",
    "name": "repo",
    "default_branch": "main",
}

CHECK_DEF_PAYLOAD = {
    "name": "Backend tests",
    "check_type": "tests",
    "command": "pytest",
    "required": True,
    "enabled": True,
    "severity": "blocking",
    "description": "Run backend unit tests",
}

CHECK_RUN_PAYLOAD_BASE = {
    "target_type": "manual",
    "target_id": "manual-run-1",
    "status": "completed",
    "conclusion": "success",
    "summary": "Tests passed",
}


def _create_project(name: str = "QAProject") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str) -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories",
        json=REPO_PAYLOAD,
    ).json()


def _create_definition(project_id: str, payload: dict | None = None) -> dict:
    return client.post(
        f"/projects/{project_id}/check-definitions",
        json=payload or CHECK_DEF_PAYLOAD,
    ).json()


# ---------------------------------------------------------------------------
# POST /projects/{id}/check-definitions
# ---------------------------------------------------------------------------

def test_create_check_definition_returns_201_and_shape():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/check-definitions",
        json=CHECK_DEF_PAYLOAD,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["name"] == "Backend tests"
    assert data["check_type"] == "tests"
    assert data["command"] == "pytest"
    assert data["required"] is True
    assert data["enabled"] is True
    assert data["severity"] == "blocking"
    assert data["description"] == "Run backend unit tests"
    assert data["code_repository_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_check_definition_with_repo_id():
    project = _create_project()
    repo = _create_repo(project["id"])
    payload = {**CHECK_DEF_PAYLOAD, "code_repository_id": repo["id"]}
    resp = client.post(f"/projects/{project['id']}/check-definitions", json=payload)
    assert resp.status_code == 201
    assert resp.json()["code_repository_id"] == repo["id"]


def test_create_check_definition_unknown_project_returns_404():
    resp = client.post(
        "/projects/nonexistent/check-definitions",
        json=CHECK_DEF_PAYLOAD,
    )
    assert resp.status_code == 404


def test_create_check_definition_unknown_repo_returns_404():
    project = _create_project()
    payload = {**CHECK_DEF_PAYLOAD, "code_repository_id": "does-not-exist"}
    resp = client.post(f"/projects/{project['id']}/check-definitions", json=payload)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/check-definitions
# ---------------------------------------------------------------------------

def test_list_project_check_definitions():
    project = _create_project()
    _create_definition(project["id"])
    _create_definition(project["id"], {**CHECK_DEF_PAYLOAD, "name": "Lint", "check_type": "lint"})
    resp = client.get(f"/projects/{project['id']}/check-definitions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    names = {d["name"] for d in items}
    assert "Backend tests" in names
    assert "Lint" in names


def test_list_project_check_definitions_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/check-definitions")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /check-definitions/{id}
# ---------------------------------------------------------------------------

def test_get_check_definition_returns_definition():
    project = _create_project()
    created = _create_definition(project["id"])
    resp = client.get(f"/check-definitions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_check_definition_missing_returns_404():
    resp = client.get("/check-definitions/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /check-definitions/{id}
# ---------------------------------------------------------------------------

def test_patch_check_definition_updates_fields():
    project = _create_project()
    created = _create_definition(project["id"])
    resp = client.patch(
        f"/check-definitions/{created['id']}",
        json={"name": "Renamed tests", "severity": "warning", "enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed tests"
    assert data["severity"] == "warning"
    assert data["enabled"] is False
    # Unchanged fields preserved
    assert data["check_type"] == "tests"
    assert data["command"] == "pytest"


def test_patch_check_definition_missing_returns_404():
    resp = client.patch(
        "/check-definitions/does-not-exist",
        json={"name": "x"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audit events for check definitions
# ---------------------------------------------------------------------------

def test_check_definition_create_writes_audit_event():
    project = _create_project()
    _create_definition(project["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "check_definition_created" for e in events)


def test_check_definition_patch_writes_audit_event():
    project = _create_project()
    created = _create_definition(project["id"])
    client.patch(f"/check-definitions/{created['id']}", json={"name": "updated"})
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "check_definition_updated" for e in events)


# ---------------------------------------------------------------------------
# POST /projects/{id}/check-definitions/from-safety-profile
# ---------------------------------------------------------------------------

def test_from_safety_profile_uses_default_when_no_profile_saved():
    """Must work when no safety profile exists — uses DEFAULT_REQUIRED_CHECKS (tests, build)."""
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={},
    )
    assert resp.status_code == 201
    data = resp.json()
    created = data["created"]
    check_types = {d["check_type"] for d in created}
    assert "tests" in check_types
    assert "build" in check_types


def test_from_safety_profile_with_saved_profile_creates_definitions():
    project = _create_project()
    repo_obj = _create_repo(project["id"])
    # Save a profile with custom required_checks
    client.post(
        f"/code-repositories/{repo_obj['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": [],
            "required_checks": ["tests", "semgrep", "gitleaks"],
            "requires_approval_for": [],
            "protected_branches": [],
            "notes": "",
        },
    )
    resp = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={"code_repository_id": repo_obj["id"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    created = data["created"]
    check_types = {d["check_type"] for d in created}
    assert "tests" in check_types
    assert "security_sast" in check_types
    assert "secret_scan" in check_types


def test_from_safety_profile_dedupes_existing_definitions():
    project = _create_project()
    # First call — creates definitions
    resp1 = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={},
    )
    assert resp1.status_code == 201
    created_first = resp1.json()["created"]
    assert len(created_first) > 0

    # Second call — same project, same keys, nothing new created
    resp2 = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert len(data2["created"]) == 0
    assert len(data2["existing"]) == len(created_first)


def test_from_safety_profile_unknown_project_returns_404():
    resp = client.post(
        "/projects/nonexistent/check-definitions/from-safety-profile",
        json={},
    )
    assert resp.status_code == 404


def test_from_safety_profile_unknown_repo_returns_404():
    project = _create_project()
    resp = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={"code_repository_id": "does-not-exist"},
    )
    assert resp.status_code == 404


def test_from_safety_profile_skips_unknown_keys():
    """Unknown required_checks values are silently skipped — no 400 or exception."""
    project = _create_project()
    repo_obj = _create_repo(project["id"])
    client.post(
        f"/code-repositories/{repo_obj['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": [],
            "required_checks": ["tests", "unknown-tool-xyz", "another-unknown"],
            "requires_approval_for": [],
            "protected_branches": [],
            "notes": "",
        },
    )
    resp = client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={"code_repository_id": repo_obj["id"]},
    )
    assert resp.status_code == 201
    data = resp.json()
    all_defs = data["created"] + data["existing"]
    # Only "tests" is known; "unknown-tool-xyz" / "another-unknown" are skipped
    assert len(all_defs) == 1
    assert all_defs[0]["check_type"] == "tests"


def test_from_safety_profile_writes_audit_events():
    project = _create_project()
    client.post(
        f"/projects/{project['id']}/check-definitions/from-safety-profile",
        json={},
    )
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    created_events = [e for e in events if e["action"] == "check_definition_created"]
    # DEFAULT_REQUIRED_CHECKS has 2 entries → 2 audit events
    assert len(created_events) >= 1


# ---------------------------------------------------------------------------
# POST /check-runs
# ---------------------------------------------------------------------------

def test_record_check_run_returns_201_and_shape():
    project = _create_project()
    payload = {**CHECK_RUN_PAYLOAD_BASE, "project_id": project["id"]}
    resp = client.post("/check-runs", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == project["id"]
    assert data["target_type"] == "manual"
    assert data["target_id"] == "manual-run-1"
    assert data["status"] == "completed"
    assert data["conclusion"] == "success"
    assert data["summary"] == "Tests passed"
    assert data["artifact_id"] is None
    assert "id" in data
    assert "started_at" in data
    assert "created_at" in data


def test_record_check_run_with_check_definition():
    project = _create_project()
    defn = _create_definition(project["id"])
    payload = {
        **CHECK_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "check_definition_id": defn["id"],
        "target_type": "project",
        "target_id": project["id"],
    }
    resp = client.post("/check-runs", json=payload)
    assert resp.status_code == 201
    assert resp.json()["check_definition_id"] == defn["id"]


def test_record_check_run_unknown_project_returns_404():
    payload = {**CHECK_RUN_PAYLOAD_BASE, "project_id": "nonexistent"}
    resp = client.post("/check-runs", json=payload)
    assert resp.status_code == 404


def test_record_check_run_unknown_check_definition_returns_404():
    project = _create_project()
    payload = {
        **CHECK_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "check_definition_id": "does-not-exist",
    }
    resp = client.post("/check-runs", json=payload)
    assert resp.status_code == 404


def test_record_check_run_unknown_repo_returns_404():
    project = _create_project()
    payload = {
        **CHECK_RUN_PAYLOAD_BASE,
        "project_id": project["id"],
        "code_repository_id": "does-not-exist",
    }
    resp = client.post("/check-runs", json=payload)
    assert resp.status_code == 404


def test_record_check_run_writes_audit_event():
    project = _create_project()
    payload = {**CHECK_RUN_PAYLOAD_BASE, "project_id": project["id"]}
    client.post("/check-runs", json=payload)
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    assert any(e["action"] == "check_run_recorded" for e in events)


# ---------------------------------------------------------------------------
# GET /projects/{id}/check-runs
# ---------------------------------------------------------------------------

def test_list_project_check_runs():
    project = _create_project()
    payload = {**CHECK_RUN_PAYLOAD_BASE, "project_id": project["id"]}
    client.post("/check-runs", json=payload)
    client.post("/check-runs", json={**payload, "summary": "Second run"})
    resp = client.get(f"/projects/{project['id']}/check-runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_project_check_runs_unknown_project_returns_404():
    resp = client.get("/projects/nonexistent/check-runs")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /check-runs/{id}
# ---------------------------------------------------------------------------

def test_get_check_run_returns_run():
    project = _create_project()
    created = client.post(
        "/check-runs",
        json={**CHECK_RUN_PAYLOAD_BASE, "project_id": project["id"]},
    ).json()
    resp = client.get(f"/check-runs/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_check_run_missing_returns_404():
    resp = client.get("/check-runs/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /dev-tasks/{id}/check-runs
# ---------------------------------------------------------------------------

def _create_dev_task_via_decomposition(project_id: str) -> dict:
    """Creates a dev_task by running a task decomposition (uses mock provider)."""
    req = client.post(
        f"/projects/{project_id}/requirements",
        json={
            "title": "Sample requirement",
            "problem_statement": "Test.",
            "business_goal": "Coverage.",
        },
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return decomp["dev_tasks"][0]


def test_list_dev_task_check_runs_filters_by_target():
    project = _create_project()
    task = _create_dev_task_via_decomposition(project["id"])

    # Record one check run targeting this dev_task
    client.post(
        "/check-runs",
        json={
            "project_id": project["id"],
            "target_type": "dev_task",
            "target_id": task["id"],
            "status": "completed",
            "conclusion": "success",
            "summary": "lint passed",
        },
    )
    # Record another for a different target
    client.post(
        "/check-runs",
        json={
            "project_id": project["id"],
            "target_type": "manual",
            "target_id": "unrelated",
            "status": "completed",
            "conclusion": "failure",
            "summary": "other",
        },
    )

    resp = client.get(f"/dev-tasks/{task['id']}/check-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["target_id"] == task["id"]
    assert runs[0]["target_type"] == "dev_task"


def test_list_dev_task_check_runs_unknown_dev_task_returns_404():
    resp = client.get("/dev-tasks/does-not-exist/check-runs")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# No command execution — defensive check
# ---------------------------------------------------------------------------

def test_check_run_does_not_execute_anything(monkeypatch):
    """Records a check run and asserts subprocess.run / os.system are never called."""
    called = []

    def fake_subprocess_run(*args, **kwargs):
        called.append(("subprocess.run", args))

    def fake_os_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(os, "system", fake_os_system)

    project = _create_project()
    resp = client.post(
        "/check-runs",
        json={**CHECK_RUN_PAYLOAD_BASE, "project_id": project["id"]},
    )
    assert resp.status_code == 201
    assert called == [], f"Unexpected external command calls: {called}"
