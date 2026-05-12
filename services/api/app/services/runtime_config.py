"""Resolved runtime configuration view (Release 8, Task 45).

Combines runtime profile, repository, artifact storage, secret provider and
execution toggles into one inspectable, sanitized response. No network
calls, no DB calls, no secrets.
"""

from __future__ import annotations

from typing import Any

from .. import config
from .runtime_profile import build_runtime_summary, is_known_profile


def _repository_section(repo_provider: str) -> dict[str, Any]:
    durable = repo_provider in ("local_document", "firestore")
    requires_cloud = repo_provider == "firestore"
    return {
        "provider": repo_provider,
        "durable": durable,
        "requires_external_cloud": requires_cloud,
    }


def _artifact_section() -> dict[str, Any]:
    provider = getattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")
    return {
        "provider": provider,
        "root": config.ARTIFACT_FILESYSTEM_ROOT if provider == "filesystem" else None,
        "durable": provider in ("filesystem", "database"),
        "max_inline_bytes": config.ARTIFACT_MAX_INLINE_BYTES,
    }


def _secrets_section() -> dict[str, Any]:
    return {
        "provider": getattr(config, "SECRET_PROVIDER", "env"),
        "github_token_configured": bool(getattr(config, "GITHUB_TOKEN", "")),
        "auth_token_secret_configured": bool(getattr(config, "AUTH_TOKEN_SECRET", "")),
    }


def _execution_section() -> dict[str, Any]:
    return {
        "command_runner_enabled": bool(config.COMMAND_RUNNER_ENABLED),
        "git_workflow_enabled": bool(config.GIT_WORKFLOW_ENABLED),
        "git_commit_enabled": bool(config.GIT_COMMIT_ENABLED),
        "openhands_execution_enabled": bool(config.OPENHANDS_EXECUTION_ENABLED),
    }


def _integrations_section(repo_provider: str) -> dict[str, Any]:
    return {
        "github_enabled": bool(config.GITHUB_INTEGRATION_ENABLED),
        "firestore_enabled": repo_provider == "firestore",
        "mongodb_enabled": repo_provider == "local_document",
        "kody_review_enabled": bool(getattr(config, "KODY_REVIEW_ENABLED", False)),
    }


def _profile_warnings(profile: str, repo_provider: str, artifact_provider: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    if not is_known_profile(profile):
        errors.append(
            f"Unknown FORGELOOP_RUNTIME_PROFILE={profile!r}. "
            f"Allowed: local, hybrid, cloud"
        )
    if profile == "local":
        if repo_provider == "memory":
            warnings.append(
                "local profile + memory repository: data is not durable."
            )
        if repo_provider == "firestore":
            warnings.append(
                "local profile + firestore repository: cloud persistence active in local mode."
            )
        if artifact_provider == "database":
            warnings.append(
                "local profile + database artifacts: large artifacts will bloat the DB; "
                "filesystem provider is recommended for durable local use."
            )
    elif profile == "cloud":
        if config.COMMAND_RUNNER_ENABLED:
            warnings.append(
                "cloud profile + command runner enabled: local command execution is risky."
            )
        if config.OPENHANDS_EXECUTION_ENABLED:
            warnings.append(
                "cloud profile + OpenHands execution enabled: local external execution is risky."
            )
        if artifact_provider == "filesystem":
            warnings.append(
                "cloud profile + filesystem artifacts: requires shared/persistent disk; "
                "verify deployment configuration."
            )
        if repo_provider == "memory":
            warnings.append("cloud profile + memory repository: data is not durable.")
    # hybrid: accepted; specific feature warnings come from runtime_profile summary
    return warnings, errors


def build_resolved_runtime_config() -> dict[str, Any]:
    """Build the resolved runtime configuration view."""
    profile = (config.FORGELOOP_RUNTIME_PROFILE or "").strip().lower()
    repo_provider = config.REPOSITORY_PROVIDER
    artifact_provider = getattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")

    extra_warnings, errors = _profile_warnings(profile, repo_provider, artifact_provider)

    # Pull warnings from the runtime profile summary so callers get a
    # complete view from one endpoint without duplicating per-feature
    # checks here.
    base_summary = build_runtime_summary()
    warnings: list[str] = list(base_summary.get("warnings", []))
    for w in extra_warnings:
        if w not in warnings:
            warnings.append(w)
    for e in base_summary.get("errors", []):
        if e not in errors:
            errors.append(e)

    return {
        "profile": profile,
        "repository": _repository_section(repo_provider),
        "artifacts": _artifact_section(),
        "secrets": _secrets_section(),
        "execution": _execution_section(),
        "integrations": _integrations_section(repo_provider),
        "warnings": warnings,
        "errors": errors,
    }
