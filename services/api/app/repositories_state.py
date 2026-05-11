"""Module-level repository singletons and shared writers.

Single source of truth for the wired-up repositories. `main.py` re-exports
these names so existing imports (`from app.main import audit_event_repo`,
the 26-name conftest import) continue to work unchanged.

The 26-tuple unpack here is preserved verbatim from the original main.py
pending the S5 Repositories container refactor.
"""

from .repositories import get_repositories
from .services.audit_writer import AuditWriter

(
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
    code_repo_repo,
    repo_safety_profile_repo,
    epic_repo,
    check_definition_repo,
    check_run_repo,
    tool_runner_definition_repo,
    tool_run_repo,
    pr_draft_repo,
    pr_review_repo,
    ci_event_repo,
    ci_analysis_repo,
    incident_repo,
    incident_analysis_repo,
    memory_learning_run_repo,
    memory_candidate_repo,
) = get_repositories()

audit_writer = AuditWriter(audit_event_repo)
