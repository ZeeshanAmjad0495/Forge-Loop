"""Cloud-profile compatibility check (Release 8, Task 46).

Validates the current runtime configuration against the requirements of
the cloud profile. Reports each check with status ``pass | warning | fail``
and never performs real GCP/network calls.
"""

from __future__ import annotations

from typing import Any, Literal

from .. import config
from .runtime_profile import is_known_profile

CheckStatus = Literal["pass", "warning", "fail"]


def _check(name: str, status: CheckStatus, message: str) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message}


def _check_profile(profile: str) -> dict[str, Any]:
    if not is_known_profile(profile):
        return _check(
            "runtime_profile",
            "fail",
            f"Unknown FORGELOOP_RUNTIME_PROFILE={profile!r}.",
        )
    return _check("runtime_profile", "pass", f"profile={profile}")


def _check_repository(profile: str) -> dict[str, Any]:
    provider = config.REPOSITORY_PROVIDER
    if profile == "cloud":
        if provider == "firestore":
            return _check("repository_provider", "pass", "firestore is cloud-durable.")
        if provider == "local_document":
            return _check(
                "repository_provider",
                "warning",
                "local_document (MongoDB) in cloud profile requires hosted MongoDB.",
            )
        if provider == "memory":
            return _check(
                "repository_provider",
                "fail",
                "memory provider is not durable; unsuitable for cloud.",
            )
    if profile in ("local", "hybrid"):
        if provider == "memory":
            return _check(
                "repository_provider",
                "warning",
                "memory provider is not durable.",
            )
        return _check("repository_provider", "pass", f"provider={provider}")
    return _check("repository_provider", "pass", f"provider={provider}")


def _check_artifacts(profile: str) -> dict[str, Any]:
    provider = getattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")
    if profile == "cloud":
        if provider == "filesystem":
            return _check(
                "artifact_provider",
                "warning",
                "filesystem artifacts in cloud profile require persistent shared disk.",
            )
        return _check("artifact_provider", "pass", f"provider={provider}")
    return _check("artifact_provider", "pass", f"provider={provider}")


def _check_command_runner(profile: str) -> dict[str, Any]:
    if config.COMMAND_RUNNER_ENABLED and profile == "cloud":
        return _check(
            "command_runner",
            "warning",
            "command runner enabled in cloud profile is risky/cloud-unsafe.",
        )
    return _check("command_runner", "pass", "disabled or non-cloud profile")


def _check_openhands(profile: str) -> dict[str, Any]:
    if config.OPENHANDS_EXECUTION_ENABLED and profile == "cloud":
        return _check(
            "openhands_execution",
            "warning",
            "OpenHands execution enabled in cloud profile is risky.",
        )
    return _check("openhands_execution", "pass", "disabled or non-cloud profile")


def _check_git_workflow(profile: str) -> dict[str, Any]:
    if config.GIT_WORKFLOW_ENABLED and profile == "cloud":
        return _check(
            "git_workflow",
            "warning",
            "git workflow enabled in cloud profile assumes a writable workspace.",
        )
    return _check("git_workflow", "pass", "disabled or non-cloud profile")


def _check_github_integration() -> dict[str, Any]:
    if not config.GITHUB_INTEGRATION_ENABLED:
        return _check("github_integration", "pass", "disabled")
    token = (config.GITHUB_TOKEN or "").strip()
    if not token:
        return _check(
            "github_integration",
            "fail",
            "GitHub integration enabled but GITHUB_TOKEN is not configured.",
        )
    return _check("github_integration", "pass", "enabled with token configured")


def _check_auth() -> dict[str, Any]:
    if not config.AUTH_ENABLED:
        return _check("auth", "warning", "auth disabled.")
    if not (config.AUTH_TOKEN_SECRET or "").strip():
        return _check("auth", "fail", "AUTH_ENABLED but AUTH_TOKEN_SECRET missing.")
    return _check("auth", "pass", "auth enabled with token secret configured")


def _check_cors() -> dict[str, Any]:
    origins = list(config.CORS_ALLOWED_ORIGINS)
    if "*" in origins:
        return _check(
            "cors_origins",
            "warning",
            "CORS_ALLOWED_ORIGINS contains '*'; restrict in cloud deployments.",
        )
    return _check("cors_origins", "pass", f"{len(origins)} origin(s) configured")


def _check_secrets_provider() -> dict[str, Any]:
    provider = getattr(config, "SECRET_PROVIDER", "env")
    return _check("secrets_provider", "pass", f"provider={provider}")


def _check_firestore_config(profile: str) -> dict[str, Any]:
    if config.REPOSITORY_PROVIDER != "firestore":
        return _check("firestore_config", "pass", "not using firestore")
    if not config.GCP_PROJECT_ID:
        if profile == "cloud":
            return _check(
                "firestore_config",
                "fail",
                "firestore provider selected but GCP_PROJECT_ID is empty.",
            )
        return _check(
            "firestore_config",
            "warning",
            "firestore provider selected but GCP_PROJECT_ID is empty.",
        )
    return _check("firestore_config", "pass", "GCP_PROJECT_ID configured")


def build_cloud_compatibility_report() -> dict[str, Any]:
    profile = (config.FORGELOOP_RUNTIME_PROFILE or "").strip().lower()

    checks = [
        _check_profile(profile),
        _check_repository(profile),
        _check_artifacts(profile),
        _check_command_runner(profile),
        _check_openhands(profile),
        _check_git_workflow(profile),
        _check_github_integration(),
        _check_auth(),
        _check_cors(),
        _check_secrets_provider(),
        _check_firestore_config(profile),
    ]

    warnings = [c["message"] for c in checks if c["status"] == "warning"]
    errors = [c["message"] for c in checks if c["status"] == "fail"]
    compatible = not errors

    return {
        "compatible": compatible,
        "profile": profile,
        "cloud_required": profile == "cloud",
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }
