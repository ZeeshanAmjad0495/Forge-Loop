import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.repositories_state import repos


@pytest.fixture(autouse=True)
def clear_repos():
    repos.reset_all()
    from app.services.cache_provider import reset_cache_provider
    from app.services.event_bus import reset_event_bus
    from app.services.workflow_engine import reset_workflow_engine

    reset_cache_provider()
    reset_event_bus()
    reset_workflow_engine()


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", False)


# ---------------------------------------------------------------------------
# Shared convenience fixtures — opt-in, not autouse
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def project(client):
    res = client.post("/projects", json={"name": "TestProject", "description": "fixture project"})
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def code_repository(client, project):
    res = client.post(
        f"/projects/{project['id']}/code-repositories",
        json={
            "provider": "github",
            "repo_url": "https://github.com/org/repo",
            "name": "repo",
            "default_branch": "main",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def repo_safety_profile(client, code_repository):
    res = client.post(
        f"/code-repositories/{code_repository['id']}/safety-profile",
        json={
            "work_safe_mode": True,
            "allowed_actions": [],
            "blocked_paths": [],
            "required_checks": ["tests"],
            "requires_approval_for": [],
            "protected_branches": ["main"],
            "notes": "",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def requirement(client, project):
    res = client.post(
        f"/projects/{project['id']}/requirements",
        json={"title": "Sample requirement", "problem_statement": "Test fixture."},
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def dev_task(client, requirement):
    res = client.post(f"/requirements/{requirement['id']}/task-decompositions")
    assert res.status_code == 201
    return res.json()["dev_tasks"][0]


@pytest.fixture
def subtask(client, dev_task):
    res = client.get(f"/dev-tasks/{dev_task['id']}/subtasks")
    assert res.status_code == 200
    items = res.json()
    return items[0] if items else None


@pytest.fixture
def check_definition(client, project):
    res = client.post(
        f"/projects/{project['id']}/check-definitions",
        json={
            "name": "Backend tests",
            "check_type": "tests",
            "command": "pytest",
            "required": True,
            "enabled": True,
            "severity": "blocking",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def tool_runner_definition(client, project):
    res = client.post(
        f"/projects/{project['id']}/tool-runner-definitions",
        json={
            "name": "OpenHands",
            "runner_type": "openhands",
            "enabled": True,
            "mode": "dry_run",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def pr_draft(client, project, code_repository, dev_task):
    res = client.post(
        f"/projects/{project['id']}/pr-drafts",
        json={
            "code_repository_id": code_repository["id"],
            "dev_task_id": dev_task["id"],
            "provider": "manual",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def ci_event(client, project):
    res = client.post(
        f"/projects/{project['id']}/ci-events",
        json={
            "provider": "github_actions",
            "status": "completed",
            "conclusion": "failure",
            "workflow_name": "CI",
            "branch": "main",
        },
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def incident(client, project):
    res = client.post(
        f"/projects/{project['id']}/incidents",
        json={
            "title": "Service outage",
            "description": "500s observed on /api/health",
            "severity": "sev2",
        },
    )
    assert res.status_code == 201
    return res.json()
