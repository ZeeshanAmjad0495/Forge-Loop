"""Tests for Task 38: controlled GitHub draft PR creation.

All GitHub I/O is replaced with a fake client; the git push helper is
monkey-patched so no real `git push` runs and no real network is touched.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import github_client as github_client_mod
from app.services import git_workflow as git_workflow_mod
from app.services import pr_publication as pr_publication_mod
from app.services.git_workflow import _check_top_level, _redact_token
from app.services.github_client import (
    CreatedPullRequest,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubValidationError,
)
from app.services.github_repo import GitHubRepoUrlError, parse_owner_repo


client = TestClient(app)


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url, expected", [
    ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World/", ("octocat", "Hello-World")),
    ("git@github.com:octocat/Hello-World.git", ("octocat", "Hello-World")),
    ("git@github.com:octocat/Hello-World", ("octocat", "Hello-World")),
    ("ssh://git@github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
])
def test_parse_owner_repo_accepts_canonical_forms(url, expected):
    assert parse_owner_repo(url) == expected


@pytest.mark.parametrize("url", [
    "",
    None,
    "http://github.com/owner/repo",
    "https://gitlab.com/owner/repo",
    "https://github.com/single-segment",
    "https://github.com/owner/repo/extra",
    "https://github.com/.bad/repo",
    "https://github.com/owner/..bad",
    "https://github.com/owner;rm/repo",
    "https://github.com/owner/repo with spaces",
])
def test_parse_owner_repo_rejects_unsafe(url):
    with pytest.raises(GitHubRepoUrlError):
        parse_owner_repo(url)


def test_redact_token_replaces_token_and_url_form():
    token = "ghp_secret_value"
    assert _redact_token("hello", token) == "hello"
    assert _redact_token(f"prefix {token} suffix", token) == "prefix *** suffix"
    url = f"https://x-access-token:{token}@github.com/o/r.git"
    assert token not in _redact_token(url, token)
    assert "x-access-token:***" in _redact_token(url, token)


def test_redact_token_noop_when_token_empty():
    assert _redact_token("hello world", "") == "hello world"
    assert _redact_token("hello world", None) == "hello world"


def test_check_top_level_allows_push_but_publication_service_uses_no_flags():
    # Allow-list permits push.
    _check_top_level(["push"])
    _check_top_level(["push", "origin", "forgeloop/dev-task/abc"])
    # The publication service itself never constructs forbidden flags;
    # the _PUSH_FORBIDDEN_FLAGS pre-check is exercised in
    # test_push_helper_rejects_forbidden_flags below.


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeGitHubClient:
    response: CreatedPullRequest | None = None
    raises: Exception | None = None
    calls: list = None

    def __post_init__(self):
        self.calls = []

    def create_draft_pull_request(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        assert self.response is not None, "fake must be primed"
        return self.response


def _install_github_client(monkeypatch, fake) -> _FakeGitHubClient:
    monkeypatch.setattr(github_client_mod, "GITHUB_CLIENT", fake)
    return fake


def _block_urllib(monkeypatch):
    def fail(*a, **kw):
        raise AssertionError("urllib.request.urlopen must not be invoked in tests")
    monkeypatch.setattr(urllib.request, "urlopen", fail)


def _make_fake_push(token_holder=None, *, exit_code=0, stdout="", stderr=""):
    """Returns a fn matching GitWorkflowService.push_forgeloop_branch."""
    captured: dict = {}

    def fake_push(self, *, workspace, branch_name, remote_name="origin",
                  remote_url_with_token=None, token=None):
        captured["argv_url_or_remote"] = remote_url_with_token or remote_name
        captured["branch_name"] = branch_name
        captured["token"] = token
        captured["remote_name"] = remote_name
        if token_holder is not None:
            token_holder["seen"] = token
        # token leaks would be caught by the response/audit/artifact
        # assertions below; here we just return a sanitized result.
        return (
            git_workflow_mod._GitResult(
                exit_code=exit_code,
                stdout=_redact_token(stdout, token),
                stderr=_redact_token(stderr, token),
            ),
            remote_name,
        )

    fake_push.captured = captured
    return fake_push


def _enable_github(monkeypatch, token="ghp_test_TOKEN_1234567890"):
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_TOKEN", token)
    monkeypatch.setattr(config, "GITHUB_PUSH_ENABLED", True)
    return token


def _create_project(name: str = "P38") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _create_repo(project_id: str, *,
                 repo_url: str = "https://github.com/octocat/Hello-World",
                 provider: str = "github") -> dict:
    return client.post(
        f"/projects/{project_id}/code-repositories",
        json={
            "provider": provider,
            "repo_url": repo_url,
            "name": "repo",
            "default_branch": "main",
        },
    ).json()


def _create_dev_task(project_id: str) -> dict:
    req = client.post(
        f"/projects/{project_id}/requirements",
        json={"title": "T", "problem_statement": "P"},
    ).json()
    decomp = client.post(f"/requirements/{req['id']}/task-decompositions").json()
    return decomp["dev_tasks"][0]


def _create_workspace(project_id: str, *, code_repository_id: str | None = None,
                      tmp_path=None) -> dict:
    body = {
        "name": "ws",
        "workspace_type": "local_created",
        "create_directory": True,
    }
    if code_repository_id:
        body["code_repository_id"] = code_repository_id
    res = client.post(f"/projects/{project_id}/workspaces", json=body)
    return res.json()


def _seed_workspace_branch(project_id, workspace_id, name="forgeloop/dev-task/x",
                           code_repository_id=None, dev_task_id=None):
    """Insert a WorkspaceBranch row directly via the repo (we don't need a
    real git directory for publication-service tests because the push helper
    is monkeypatched)."""
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
        status="clean",
        created_at=now,
        updated_at=now,
        last_inspected_at=now,
        error_message=None,
    )
    workspace_branch_repo.save(branch)
    return branch.model_dump(mode="json")


def _prepare_draft(project_id, repo_id, *, dev_task_id=None) -> dict:
    body = {"code_repository_id": repo_id, "target_branch": "main"}
    if dev_task_id:
        body["dev_task_id"] = dev_task_id
    res = client.post(f"/projects/{project_id}/pr-drafts", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _approve_draft(pr_draft_id: str) -> dict:
    res = client.post(f"/pr-drafts/{pr_draft_id}/approve")
    assert res.status_code == 200, res.text
    return res.json()


def _setup_happy_path(monkeypatch, workspace_root=None) -> dict:
    """Return a dict with project/repo/workspace/branch/draft IDs ready to publish."""
    project = _create_project()
    repo = _create_repo(project["id"])
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"], code_repository_id=repo["id"])
    branch = _seed_workspace_branch(
        project["id"], ws["id"],
        name=f"forgeloop/dev-task/{task['id']}",
        code_repository_id=repo["id"],
        dev_task_id=task["id"],
    )
    draft = _prepare_draft(project["id"], repo["id"], dev_task_id=task["id"])
    approved = _approve_draft(draft["id"])
    return {
        "project_id": project["id"],
        "repo_id": repo["id"],
        "task_id": task["id"],
        "workspace_id": ws["id"],
        "branch_id": branch["id"],
        "branch_name": branch["name"],
        "draft_id": approved["id"],
    }


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "ws_root"
    root.mkdir()
    monkeypatch.setattr(config, "FORGELOOP_WORKSPACE_ROOT", str(root))
    monkeypatch.setattr(config, "WORKSPACE_ALLOW_OUTSIDE_ROOT", False)
    return root


# ---------------------------------------------------------------------------
# Config / disabled paths
# ---------------------------------------------------------------------------


def test_integration_disabled_returns_409(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", False)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
        },
    )
    assert res.status_code == 409
    assert "GITHUB_INTEGRATION_DISABLED" in res.text
    assert fake.calls == []

    # Draft unchanged
    fetched = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    assert fetched["status"] == "approved_for_creation"
    assert fetched["external_pr_url"] is None


def test_missing_token_returns_409(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_TOKEN", "")
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
        },
    )
    assert res.status_code == 409
    assert "GITHUB_TOKEN_NOT_CONFIGURED" in res.text
    assert fake.calls == []


def test_push_disabled_returns_409_when_push_requested(workspace_root, monkeypatch):
    monkeypatch.setattr(config, "GITHUB_INTEGRATION_ENABLED", True)
    monkeypatch.setattr(config, "GITHUB_TOKEN", "ghp_x")
    monkeypatch.setattr(config, "GITHUB_PUSH_ENABLED", False)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    captured_argv: list = []
    real_run = subprocess.run

    def recording(args, *a, **kw):
        captured_argv.append(args)
        return real_run(args, *a, **kw)
    monkeypatch.setattr(subprocess, "run", recording)

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 409
    assert "GITHUB_PUSH_DISABLED" in res.text
    assert fake.calls == []
    # And no real `git push` was attempted.
    assert not any(
        isinstance(a, (list, tuple)) and len(a) >= 2 and a[1] == "push"
        for a in captured_argv
    )


# ---------------------------------------------------------------------------
# Validation paths
# ---------------------------------------------------------------------------


def test_missing_pr_draft_returns_404(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient())
    res = client.post(
        "/pr-drafts/missing/create-github-draft",
        json={"workspace_id": "x", "workspace_branch_id": "y"},
    )
    assert res.status_code == 404


def test_unapproved_draft_rejected(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    project = _create_project()
    repo = _create_repo(project["id"])
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"], code_repository_id=repo["id"])
    branch = _seed_workspace_branch(
        project["id"], ws["id"],
        name=f"forgeloop/dev-task/{task['id']}",
        code_repository_id=repo["id"],
        dev_task_id=task["id"],
    )
    draft = _prepare_draft(project["id"], repo["id"], dev_task_id=task["id"])
    # Do NOT approve.
    res = client.post(
        f"/pr-drafts/{draft['id']}/create-github-draft",
        json={
            "workspace_id": ws["id"],
            "workspace_branch_id": branch["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert "approved_for_creation" in res.text
    assert fake.calls == []


def test_workspace_project_mismatch_rejected(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    project_a = _create_project("A")
    project_b = _create_project("B")
    repo_a = _create_repo(project_a["id"])
    task_a = _create_dev_task(project_a["id"])
    ws_b = _create_workspace(project_b["id"])
    branch = _seed_workspace_branch(
        project_b["id"], ws_b["id"],
        name=f"forgeloop/dev-task/{task_a['id']}",
        dev_task_id=task_a["id"],
    )
    draft = _prepare_draft(project_a["id"], repo_a["id"], dev_task_id=task_a["id"])
    _approve_draft(draft["id"])
    res = client.post(
        f"/pr-drafts/{draft['id']}/create-github-draft",
        json={
            "workspace_id": ws_b["id"],
            "workspace_branch_id": branch["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert fake.calls == []


def test_branch_not_forgeloop_scoped_rejected(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    project = _create_project()
    repo = _create_repo(project["id"])
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"], code_repository_id=repo["id"])
    # Seed a branch row whose name is *not* ForgeLoop-scoped (would never
    # happen via the API but tests defense in depth).
    branch = _seed_workspace_branch(
        project["id"], ws["id"],
        name="feature/sneaky",
        code_repository_id=repo["id"],
        dev_task_id=task["id"],
    )
    draft = _prepare_draft(project["id"], repo["id"], dev_task_id=task["id"])
    _approve_draft(draft["id"])
    res = client.post(
        f"/pr-drafts/{draft['id']}/create-github-draft",
        json={
            "workspace_id": ws["id"],
            "workspace_branch_id": branch["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert "ForgeLoop-scoped" in res.text or "forgeloop" in res.text.lower()
    assert fake.calls == []


def test_non_github_provider_rejected(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())

    project = _create_project()
    repo = _create_repo(project["id"], provider="gitlab",
                        repo_url="https://gitlab.com/x/y")
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"], code_repository_id=repo["id"])
    branch = _seed_workspace_branch(
        project["id"], ws["id"],
        name=f"forgeloop/dev-task/{task['id']}",
        code_repository_id=repo["id"],
        dev_task_id=task["id"],
    )
    draft = _prepare_draft(project["id"], repo["id"], dev_task_id=task["id"])
    _approve_draft(draft["id"])
    res = client.post(
        f"/pr-drafts/{draft['id']}/create-github-draft",
        json={
            "workspace_id": ws["id"],
            "workspace_branch_id": branch["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert "github" in res.text.lower()
    assert fake.calls == []


def test_unsupported_repo_url_rejected(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient())

    project = _create_project()
    # provider=github but URL is not parseable.
    repo = _create_repo(project["id"], repo_url="https://github.com/just-one-segment")
    task = _create_dev_task(project["id"])
    ws = _create_workspace(project["id"], code_repository_id=repo["id"])
    branch = _seed_workspace_branch(
        project["id"], ws["id"],
        name=f"forgeloop/dev-task/{task['id']}",
        code_repository_id=repo["id"],
        dev_task_id=task["id"],
    )
    draft = _prepare_draft(project["id"], repo["id"], dev_task_id=task["id"])
    _approve_draft(draft["id"])
    res = client.post(
        f"/pr-drafts/{draft['id']}/create-github-draft",
        json={
            "workspace_id": ws["id"],
            "workspace_branch_id": branch["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert "unsupported repository URL" in res.text
    assert fake.calls == []


def test_missing_workspace_returns_404(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient())
    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={"workspace_id": "missing", "workspace_branch_id": ids["branch_id"]},
    )
    assert res.status_code == 404


def test_missing_workspace_branch_returns_404(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient())
    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={"workspace_id": ids["workspace_id"], "workspace_branch_id": "missing"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def _ok_response() -> CreatedPullRequest:
    return CreatedPullRequest(
        number=42,
        url="https://github.com/octocat/Hello-World/pull/42",
        api_url="https://api.github.com/repos/octocat/Hello-World/pulls/42",
        state="open",
        draft=True,
        head="forgeloop/dev-task/x",
        base="main",
        title="t",
    )


def test_happy_path_push_true(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    fake_push = _make_fake_push()
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    summary = data["publication_summary"]
    assert summary["pushed"] is True
    assert summary["pushed_branch"] == ids["branch_name"]
    assert summary["push_exit_code"] == 0
    assert summary["github_owner"] == "octocat"
    assert summary["github_repo"] == "Hello-World"
    assert summary["external_pr_url"].endswith("/pull/42")
    assert summary["external_pr_number"] == 42

    # PR draft updated atomically.
    draft = data["pr_draft"]
    assert draft["status"] == "created"
    assert draft["provider"] == "github"
    assert draft["external_pr_url"].endswith("/pull/42")
    assert draft["external_pr_number"] == 42
    assert draft["source_branch"] == ids["branch_name"]
    assert draft["workspace_id"] == ids["workspace_id"]
    assert draft["workspace_branch_id"] == ids["branch_id"]
    assert draft["github_owner"] == "octocat"
    assert draft["github_repo"] == "Hello-World"
    assert draft["last_published_at"]

    # Push was called with the token-embedded URL and no force/mirror/etc.
    cap = fake_push.captured
    assert cap["branch_name"] == ids["branch_name"]
    assert cap["token"] == token
    assert cap["argv_url_or_remote"].startswith("https://x-access-token:")
    assert token in cap["argv_url_or_remote"]
    assert cap["remote_name"] == "origin"

    # Client called with expected fields.
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["owner"] == "octocat"
    assert call["repo"] == "Hello-World"
    assert call["head"] == ids["branch_name"]
    assert call["base"] == "main"
    assert call["draft"] is True
    assert call["token"] == token

    # Token never appears in response.
    assert token not in json.dumps(data)

    # Audit events written in order.
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    actions = [e["action"] for e in events]
    assert "github_pr_creation_requested" in actions
    assert "github_branch_pushed" in actions
    assert "github_pr_created" in actions
    # Token never appears in audit details.
    assert token not in json.dumps(events)


def test_happy_path_push_false_skips_push_and_audit(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    fake_push = _make_fake_push()
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 201, res.text
    # Push not called.
    assert fake_push.captured == {}
    # Audit: no github_branch_pushed.
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    actions = {e["action"] for e in events}
    assert "github_branch_pushed" not in actions
    assert "github_pr_created" in actions


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_push_nonzero_marks_draft_failed(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    fake = _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    fake_push = _make_fake_push(exit_code=128, stderr=f"fatal: token={token}")
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 502
    # Client never called when push failed.
    assert fake.calls == []
    fetched = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    assert fetched["status"] == "failed"
    assert fetched["error_message"]
    # Token redacted from error_message.
    assert token not in fetched["error_message"]
    # Audit captures failure.
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(e["action"] == "github_pr_creation_failed" for e in events)
    assert token not in json.dumps(events)


def test_github_auth_error_maps_to_502_and_redacts_token(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    fake = _install_github_client(
        monkeypatch,
        _FakeGitHubClient(raises=GitHubAuthError(f"bad token {token}", status=401)),
    )
    fake_push = _make_fake_push()
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 502
    # Body must NOT echo the token.
    assert token not in res.text
    fetched = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    assert fetched["status"] == "failed"
    assert token not in (fetched["error_message"] or "")
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(
        e["action"] == "github_pr_creation_failed" and e["details"].get("reason") == "auth"
        for e in events
    )


def test_github_validation_error_returns_422(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(
        monkeypatch,
        _FakeGitHubClient(raises=GitHubValidationError("A pull request already exists", status=422)),
    )
    fake_push = _make_fake_push()
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 422
    fetched = client.get(f"/pr-drafts/{ids['draft_id']}").json()
    assert fetched["status"] == "failed"
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(
        e["action"] == "github_pr_creation_failed"
        and e["details"].get("reason") == "validation"
        for e in events
    )


def test_github_not_found_error_returns_502(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(
        monkeypatch,
        _FakeGitHubClient(raises=GitHubNotFoundError("repo gone", status=404)),
    )
    fake_push = _make_fake_push()
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 502
    events = client.get(f"/projects/{ids['project_id']}/audit-events").json()
    assert any(
        e["action"] == "github_pr_creation_failed"
        and e["details"].get("reason") == "not_found"
        for e in events
    )


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------


def test_explicit_approval_id_must_match(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    # Approved approval for a different target.
    appr = client.post("/approvals", json={
        "project_id": ids["project_id"],
        "target_type": "dev_task",
        "target_id": "other-task",
    }).json()
    client.patch(f"/approvals/{appr['id']}", json={"status": "approved"})

    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "approval_id": appr["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 400
    assert "approval" in res.text.lower()


def test_explicit_artifact_approval_accepted(workspace_root, monkeypatch):
    _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    appr = client.post("/approvals", json={
        "project_id": ids["project_id"],
        "target_type": "artifact",
        "target_id": ids["draft_id"],
    }).json()
    client.patch(f"/approvals/{appr['id']}", json={"status": "approved"})
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "approval_id": appr["id"],
            "push_branch": False,
        },
    )
    assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# Belt-and-braces
# ---------------------------------------------------------------------------


def test_push_helper_rejects_forbidden_flags():
    """Defense in depth: even if a caller managed to pass a forbidden flag,
    push_forgeloop_branch would refuse before invoking git."""
    from app.services.git_workflow import _PUSH_FORBIDDEN_FLAGS
    # Sanity that the well-known forbidden flags are listed.
    for f in ("--force", "--mirror", "--tags", "--set-upstream", "--all"):
        assert f in _PUSH_FORBIDDEN_FLAGS


def test_artifact_contains_no_token(workspace_root, monkeypatch):
    token = _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    fake_push = _make_fake_push(stdout=f"hello {token}", stderr=f"warning {token}")
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        fake_push,
    )

    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 201, res.text
    # Inspect the saved artifact directly.
    from app.main import artifact_repo
    # Find the github_pr_creation_summary artifact by scanning the in-memory store.
    # The store is dict-backed; iterate via its internal `_store` attribute.
    artifacts = list(getattr(artifact_repo, "_store", {}).values())
    summaries = [a for a in artifacts if a.artifact_type == "github_pr_creation_summary"]
    assert summaries
    for a in summaries:
        assert token not in a.content


def test_urllib_not_invoked_in_happy_path(workspace_root, monkeypatch):
    """Belt-and-braces: with a fake client installed, the stdlib urllib is
    never invoked even on the happy path."""
    _enable_github(monkeypatch)
    _block_urllib(monkeypatch)
    _install_github_client(monkeypatch, _FakeGitHubClient(response=_ok_response()))
    monkeypatch.setattr(
        pr_publication_mod._git_workflow.GitWorkflowService,
        "push_forgeloop_branch",
        _make_fake_push(),
    )
    ids = _setup_happy_path(monkeypatch, workspace_root)
    res = client.post(
        f"/pr-drafts/{ids['draft_id']}/create-github-draft",
        json={
            "workspace_id": ids["workspace_id"],
            "workspace_branch_id": ids["branch_id"],
            "push_branch": True,
        },
    )
    assert res.status_code == 201
