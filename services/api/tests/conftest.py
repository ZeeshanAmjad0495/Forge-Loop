import pytest
from app.main import agent_run_repo, artifact_repo, repo


@pytest.fixture(autouse=True)
def clear_repos():
    for r in (repo, agent_run_repo, artifact_repo):
        if hasattr(r, "_store"):
            r._store.clear()
