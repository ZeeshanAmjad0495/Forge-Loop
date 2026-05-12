"""Work-safe policy service (Release 12, Task 73).

Policy primitives for marketable hardening. Service computes an effective
policy for a project (most-recently-updated active project policy, else
most-recently-updated active global policy) and answers simple action
checks. It does NOT broadly enforce policy across the rest of the API yet —
callers must opt in.
"""

from __future__ import annotations

import fnmatch
import re
import uuid
from datetime import datetime, timezone

from ..models import (
    WorkSafeActionType,
    WorkSafeCheckRequest,
    WorkSafeCheckResponse,
    WorkSafePolicy,
    WorkSafePolicyCreate,
    WorkSafePolicyUpdate,
)
from ..repositories import WorkSafePolicyRepository


def create_policy(
    repo: WorkSafePolicyRepository, *, body: WorkSafePolicyCreate
) -> WorkSafePolicy:
    now = datetime.now(timezone.utc)
    policy = WorkSafePolicy(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        name=body.name,
        status=body.status,
        policy_level=body.policy_level,
        require_approval_for=list(body.require_approval_for),
        restricted_providers=list(body.restricted_providers),
        restricted_integrations=list(body.restricted_integrations),
        blocked_path_patterns=list(body.blocked_path_patterns),
        sensitive_field_patterns=list(body.sensitive_field_patterns),
        allow_external_llms=body.allow_external_llms,
        allow_cloud_storage=body.allow_cloud_storage,
        allow_github_push=body.allow_github_push,
        allow_openhands_execution=body.allow_openhands_execution,
        audit_export_enabled=body.audit_export_enabled,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    repo.save(policy)
    return policy


def update_policy(
    repo: WorkSafePolicyRepository,
    policy: WorkSafePolicy,
    body: WorkSafePolicyUpdate,
) -> WorkSafePolicy:
    data = policy.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = WorkSafePolicy(**data)
    repo.update(updated)
    return updated


def archive_policy(
    repo: WorkSafePolicyRepository, policy: WorkSafePolicy
) -> WorkSafePolicy:
    now = datetime.now(timezone.utc)
    data = policy.model_dump()
    data["status"] = "archived"
    data["archived_at"] = now
    data["updated_at"] = now
    updated = WorkSafePolicy(**data)
    repo.update(updated)
    return updated


def effective_policy(
    repo: WorkSafePolicyRepository, project_id: str
) -> WorkSafePolicy | None:
    """Return the active project policy if one exists, otherwise the active
    global policy. The most recently updated active policy wins.
    """
    project_policies = [
        p for p in repo.list_by_project(project_id) if p.status == "active"
    ]
    if project_policies:
        return max(project_policies, key=lambda p: p.updated_at)
    global_policies = [p for p in repo.list_global() if p.status == "active"]
    if global_policies:
        return max(global_policies, key=lambda p: p.updated_at)
    return None


# Mapping from action types to the policy flag that, when False, denies it.
_ACTION_ALLOW_FLAG: dict[WorkSafeActionType, str] = {
    "external_llm_call": "allow_external_llms",
    "github_push": "allow_github_push",
    "openhands_execution": "allow_openhands_execution",
    "cloud_storage": "allow_cloud_storage",
    "audit_export": "audit_export_enabled",
}


def check_action(
    policy: WorkSafePolicy | None, request: WorkSafeCheckRequest
) -> WorkSafeCheckResponse:
    reasons: list[str] = []
    if policy is None:
        return WorkSafeCheckResponse(
            action=request.action,
            decision="allow",
            policy_id=None,
            policy_level=None,
            reasons=["No active work-safe policy; default allow."],
        )

    flag = _ACTION_ALLOW_FLAG.get(request.action)
    if flag is not None and getattr(policy, flag) is False:
        reasons.append(f"Action {request.action!r} disabled by policy flag {flag!r}.")
        return WorkSafeCheckResponse(
            action=request.action,
            decision="deny",
            policy_id=policy.id,
            policy_level=policy.policy_level,
            reasons=reasons,
        )

    if request.provider and request.provider in policy.restricted_providers:
        reasons.append(f"Provider {request.provider!r} is restricted.")
        return WorkSafeCheckResponse(
            action=request.action,
            decision="deny",
            policy_id=policy.id,
            policy_level=policy.policy_level,
            reasons=reasons,
        )

    if request.integration and request.integration in policy.restricted_integrations:
        reasons.append(f"Integration {request.integration!r} is restricted.")
        return WorkSafeCheckResponse(
            action=request.action,
            decision="deny",
            policy_id=policy.id,
            policy_level=policy.policy_level,
            reasons=reasons,
        )

    if request.target_path:
        for pattern in policy.blocked_path_patterns:
            if _matches_path(request.target_path, pattern):
                reasons.append(
                    f"Target path {request.target_path!r} matches blocked pattern {pattern!r}."
                )
                return WorkSafeCheckResponse(
                    action=request.action,
                    decision="deny",
                    policy_id=policy.id,
                    policy_level=policy.policy_level,
                    reasons=reasons,
                )

    if request.action in policy.require_approval_for:
        reasons.append(f"Action {request.action!r} requires approval under this policy.")
        return WorkSafeCheckResponse(
            action=request.action,
            decision="require_approval",
            policy_id=policy.id,
            policy_level=policy.policy_level,
            reasons=reasons,
        )

    return WorkSafeCheckResponse(
        action=request.action,
        decision="allow",
        policy_id=policy.id,
        policy_level=policy.policy_level,
        reasons=["Allowed by current policy."],
    )


def _matches_path(path: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(path, pattern):
        return True
    try:
        return re.search(pattern, path) is not None
    except re.error:
        return False
