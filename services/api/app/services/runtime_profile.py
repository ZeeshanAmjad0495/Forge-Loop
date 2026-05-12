"""Runtime profile inspection service (Release 8, Task 41).

Produces a sanitized summary of the active runtime profile and its
configuration. Pure function over current config values — no I/O, no
external network, no DB calls.
"""

from __future__ import annotations

from typing import Any

from .. import config

ALLOWED_PROFILES = ("local", "hybrid", "cloud")


def _normalize_profile(raw: str) -> str:
    return (raw or "").strip().lower()


def is_known_profile(profile: str) -> bool:
    return _normalize_profile(profile) in ALLOWED_PROFILES


def _add(warnings: list[str], errors: list[str], *, warn: str | None = None, err: str | None = None) -> None:
    if warn:
        warnings.append(warn)
    if err:
        errors.append(err)


def build_runtime_summary() -> dict[str, Any]:
    """Return a sanitized runtime profile summary dict.

    Field names are stable and used by the `GET /runtime/profile` endpoint
    and by tests. Secrets are never included; only booleans that indicate
    whether a credential has been configured.
    """
    profile = _normalize_profile(config.FORGELOOP_RUNTIME_PROFILE)
    repository_provider = config.REPOSITORY_PROVIDER
    artifact_provider = getattr(config, "ARTIFACT_STORAGE_PROVIDER", "database")

    warnings: list[str] = []
    errors: list[str] = []

    if not is_known_profile(profile):
        errors.append(
            f"Unknown FORGELOOP_RUNTIME_PROFILE={profile!r}. "
            f"Allowed: {', '.join(ALLOWED_PROFILES)}"
        )

    firestore_required = repository_provider == "firestore"
    mongodb_required = repository_provider == "local_document"

    command_runner = bool(config.COMMAND_RUNNER_ENABLED)
    git_workflow = bool(config.GIT_WORKFLOW_ENABLED)
    git_commit = bool(config.GIT_COMMIT_ENABLED)
    openhands = bool(config.OPENHANDS_EXECUTION_ENABLED)
    github = bool(config.GITHUB_INTEGRATION_ENABLED)

    if profile == "local":
        if repository_provider == "memory":
            warnings.append(
                "Repository provider 'memory' is not durable; data is lost on restart."
            )
        if repository_provider == "firestore":
            warnings.append(
                "Local profile is using Firestore; cloud persistence is active."
            )
        if github:
            warnings.append(
                "GitHub integration is enabled in local profile; external network calls may occur."
            )
    elif profile == "cloud":
        if command_runner:
            warnings.append(
                "Command runner is enabled in cloud profile; local command execution is risky in cloud deployments."
            )
        if openhands:
            warnings.append(
                "OpenHands execution is enabled in cloud profile; local external execution is risky in cloud deployments."
            )
        if git_workflow:
            warnings.append(
                "Git workflow is enabled in cloud profile; local git execution assumes a writable workspace."
            )
        if repository_provider == "memory":
            warnings.append(
                "Cloud profile with memory repository: data is not durable."
            )
        if getattr(config, "FORGELOOP_WORKSPACE_ROOT", "") and not _is_absolute_workspace_root(
            config.FORGELOOP_WORKSPACE_ROOT
        ):
            # Don't fail; just inform.
            warnings.append(
                "Cloud profile with a relative workspace root; deployment must ensure a writable path."
            )
    # hybrid: accepted; rely on explicit feature warnings below

    if openhands and profile != "cloud":
        warnings.append("OpenHands execution is enabled; local external execution is active.")
    if git_workflow and profile == "local":
        warnings.append("Git workflow is enabled; local git execution is active.")

    secret_provider = getattr(config, "SECRET_PROVIDER", "env")
    github_token_configured = bool(getattr(config, "GITHUB_TOKEN", ""))

    summary: dict[str, Any] = {
        "profile": profile,
        "repository_provider": repository_provider,
        "artifact_provider": artifact_provider,
        "workspace_root": config.FORGELOOP_WORKSPACE_ROOT,
        "command_runner_enabled": command_runner,
        "git_workflow_enabled": git_workflow,
        "git_commit_enabled": git_commit,
        "openhands_execution_enabled": openhands,
        "github_integration_enabled": github,
        "firestore_required": firestore_required,
        "mongodb_required": mongodb_required,
        "secret_provider": secret_provider,
        "github_token_configured": github_token_configured,
        "warnings": warnings,
        "errors": errors,
    }
    return summary


def _is_absolute_workspace_root(path: str) -> bool:
    return path.startswith("/")


def startup_log_line() -> str:
    """Return a single sanitized log line summarizing the runtime profile."""
    s = build_runtime_summary()
    return (
        f"ForgeLoop runtime profile={s['profile']} "
        f"repository_provider={s['repository_provider']} "
        f"artifact_provider={s['artifact_provider']} "
        f"command_runner={str(s['command_runner_enabled']).lower()} "
        f"openhands={str(s['openhands_execution_enabled']).lower()} "
        f"github={str(s['github_integration_enabled']).lower()}"
    )
