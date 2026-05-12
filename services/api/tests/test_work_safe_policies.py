from app.models import (
    WorkSafeCheckRequest,
    WorkSafePolicyCreate,
    WorkSafePolicyUpdate,
)
from app.repositories import InMemoryWorkSafePolicyRepository
from app.services.work_safe_policies import (
    archive_policy,
    check_action,
    create_policy,
    effective_policy,
    update_policy,
)


# -- service unit tests ---------------------------------------------------


def test_create_policy_defaults():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo, body=WorkSafePolicyCreate(name="default", project_id="p1")
    )
    assert policy.status == "draft"
    assert policy.policy_level == "personal"
    assert policy.allow_external_llms is True


def test_effective_policy_prefers_project_over_global():
    repo = InMemoryWorkSafePolicyRepository()
    global_policy = create_policy(
        repo, body=WorkSafePolicyCreate(name="g", status="active")
    )
    project_policy = create_policy(
        repo,
        body=WorkSafePolicyCreate(name="p", project_id="p1", status="active"),
    )
    eff = effective_policy(repo, "p1")
    assert eff is not None
    assert eff.id == project_policy.id

    # Different project falls back to global
    eff_other = effective_policy(repo, "p2")
    assert eff_other is not None
    assert eff_other.id == global_policy.id


def test_effective_policy_none_when_inactive():
    repo = InMemoryWorkSafePolicyRepository()
    create_policy(repo, body=WorkSafePolicyCreate(name="draft-only"))
    assert effective_policy(repo, "p1") is None


def test_check_action_allows_when_no_policy():
    response = check_action(
        None, WorkSafeCheckRequest(action="external_llm_call")
    )
    assert response.decision == "allow"


def test_check_action_denies_disabled_action():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo,
        body=WorkSafePolicyCreate(
            name="strict",
            status="active",
            policy_level="strict",
            allow_external_llms=False,
        ),
    )
    response = check_action(
        policy, WorkSafeCheckRequest(action="external_llm_call")
    )
    assert response.decision == "deny"
    assert response.policy_level == "strict"


def test_check_action_denies_restricted_provider():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo,
        body=WorkSafePolicyCreate(
            name="x",
            status="active",
            restricted_providers=["kimi"],
        ),
    )
    response = check_action(
        policy,
        WorkSafeCheckRequest(action="external_llm_call", provider="kimi"),
    )
    assert response.decision == "deny"


def test_check_action_denies_blocked_path_pattern():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo,
        body=WorkSafePolicyCreate(
            name="x",
            status="active",
            blocked_path_patterns=["secrets/*", ".env"],
        ),
    )
    response = check_action(
        policy,
        WorkSafeCheckRequest(action="artifact_export", target_path="secrets/key.pem"),
    )
    assert response.decision == "deny"


def test_check_action_requires_approval():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo,
        body=WorkSafePolicyCreate(
            name="x",
            status="active",
            require_approval_for=["github_push"],
        ),
    )
    response = check_action(
        policy, WorkSafeCheckRequest(action="github_push")
    )
    assert response.decision == "require_approval"


def test_check_action_allow_default():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(
        repo, body=WorkSafePolicyCreate(name="x", status="active")
    )
    response = check_action(
        policy, WorkSafeCheckRequest(action="command_execution")
    )
    assert response.decision == "allow"


def test_update_policy_modifies_fields():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(repo, body=WorkSafePolicyCreate(name="x"))
    updated = update_policy(
        repo,
        policy,
        WorkSafePolicyUpdate(
            allow_external_llms=False,
            restricted_providers=["kimi"],
            status="active",
        ),
    )
    assert updated.allow_external_llms is False
    assert updated.restricted_providers == ["kimi"]


def test_archive_policy_sets_archived_at():
    repo = InMemoryWorkSafePolicyRepository()
    policy = create_policy(repo, body=WorkSafePolicyCreate(name="x"))
    archived = archive_policy(repo, policy)
    assert archived.status == "archived"
    assert archived.archived_at is not None


# -- API tests ------------------------------------------------------------


def test_create_policy_via_api(client, project):
    res = client.post(
        "/work-safe-policies",
        json={
            "name": "strict",
            "project_id": project["id"],
            "status": "active",
            "policy_level": "strict",
            "allow_external_llms": False,
        },
    )
    assert res.status_code == 201
    assert res.json()["allow_external_llms"] is False


def test_create_policy_unknown_project_404(client):
    res = client.post(
        "/work-safe-policies",
        json={"name": "x", "project_id": "missing"},
    )
    assert res.status_code == 404


def test_effective_endpoint_returns_project_policy(client, project):
    project_id = project["id"]
    client.post(
        "/work-safe-policies",
        json={"name": "g", "status": "active"},
    )
    proj_policy = client.post(
        "/work-safe-policies",
        json={"name": "p", "project_id": project_id, "status": "active"},
    ).json()
    res = client.get(
        f"/projects/{project_id}/work-safe-policy/effective"
    ).json()
    assert res is not None
    assert res["id"] == proj_policy["id"]


def test_check_endpoint_denies_blocked_path(client, project):
    project_id = project["id"]
    client.post(
        "/work-safe-policies",
        json={
            "name": "p",
            "project_id": project_id,
            "status": "active",
            "blocked_path_patterns": [".env", "secrets/*"],
        },
    )
    res = client.post(
        f"/projects/{project_id}/work-safe-policy/check",
        json={"action": "artifact_export", "target_path": "secrets/key.pem"},
    ).json()
    assert res["decision"] == "deny"


def test_check_endpoint_allows_when_no_policy(client, project):
    res = client.post(
        f"/projects/{project['id']}/work-safe-policy/check",
        json={"action": "external_llm_call"},
    ).json()
    assert res["decision"] == "allow"


def test_list_filter_by_project(client, project):
    project_id = project["id"]
    client.post(
        "/work-safe-policies",
        json={"name": "g", "status": "active"},
    )
    client.post(
        "/work-safe-policies",
        json={"name": "p", "project_id": project_id, "status": "active"},
    )
    by_project = client.get(
        f"/projects/{project_id}/work-safe-policies"
    ).json()
    assert len(by_project) == 1


def test_patch_and_archive(client):
    created = client.post(
        "/work-safe-policies", json={"name": "x"}
    ).json()
    patched = client.patch(
        f"/work-safe-policies/{created['id']}",
        json={"status": "active", "allow_github_push": False},
    ).json()
    assert patched["allow_github_push"] is False
    archived = client.post(
        f"/work-safe-policies/{created['id']}/archive"
    ).json()
    assert archived["status"] == "archived"
