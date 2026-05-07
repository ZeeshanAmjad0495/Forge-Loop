import pytest
from app import config
from app.main import (
    agent_run_repo,
    analysis_repo,
    approval_repo,
    artifact_repo,
    audit_event_repo,
    dev_task_repo,
    project_context_repo,
    project_repo,
    repo,
    requirement_repo,
    subtask_repo,
)


@pytest.fixture(autouse=True)
def clear_repos():
    for r in (
        repo,
        agent_run_repo,
        artifact_repo,
        project_repo,
        project_context_repo,
        analysis_repo,
        requirement_repo,
        dev_task_repo,
        subtask_repo,
        approval_repo,
        audit_event_repo,
    ):
        if hasattr(r, "_store"):
            r._store.clear()


@pytest.fixture(autouse=True)
def disable_auth_by_default(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ENABLED", False)
