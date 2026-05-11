from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AuditActorType = Literal["user", "system", "agent"]
AuditAction = Literal[
    "requirement_created",
    "requirement_analyzed",
    "task_decomposition_created",
    "dev_task_updated",
    "dev_task_assigned",
    "subtask_updated",
    "subtask_assigned",
    "approval_requested",
    "approval_approved",
    "approval_rejected",
    "approval_needs_revision",
    "change_requested",
    "code_repository_created",
    "code_repository_updated",
    "repo_safety_profile_updated",
    "requirement_generation_created",
    "epic_created",
    "epic_updated",
    "check_definition_created",
    "check_definition_updated",
    "check_run_recorded",
    "tool_runner_definition_created",
    "tool_runner_definition_updated",
    "tool_run_recorded",
    "openhands_package_prepared",
    "openhands_result_recorded",
    "openhands_execution_requested",
    "openhands_execution_started",
    "openhands_execution_completed",
    "openhands_execution_failed",
    "openhands_execution_timed_out",
    "openhands_execution_blocked",
    "git_inspection_completed",
    "workspace_branch_created",
    "workspace_branch_inspected",
    "workspace_commit_prepared",
    "workspace_commit_created",
    "workspace_commit_failed",
    "git_operation_blocked",
    "github_pr_creation_requested",
    "github_branch_pushed",
    "github_pr_created",
    "github_pr_creation_failed",
    "github_pr_creation_blocked",
    "pr_draft_prepared",
    "pr_draft_updated",
    "pr_draft_approved",
    "pr_review_requested",
    "pr_review_recorded",
    "pr_review_completed",
    "ci_event_recorded",
    "ci_analysis_requested",
    "ci_analysis_completed",
    "ci_analysis_failed",
    "incident_recorded",
    "incident_updated",
    "incident_analysis_requested",
    "incident_analysis_completed",
    "incident_analysis_failed",
    "remediation_work_item_prepared",
    "memory_learning_requested",
    "memory_learning_completed",
    "memory_learning_failed",
    "memory_candidate_created",
    "memory_candidate_approved",
    "memory_candidate_rejected",
    "project_memory_learned",
    "workspace_created",
    "workspace_registered",
    "workspace_inspected",
    "workspace_archived",
    "workspace_invalid",
    "command_definition_created",
    "command_definition_updated",
    "command_run_requested",
    "command_run_blocked",
    "command_run_completed",
    "command_run_failed",
    "command_run_timed_out",
    "check_execution_requested",
    "check_execution_completed",
    "check_execution_failed",
    "check_execution_blocked",
]


class AuditEvent(BaseModel):
    id: str
    project_id: str | None = None
    actor_type: AuditActorType
    actor_id: str
    action: AuditAction
    target_type: str
    target_id: str
    details: dict = {}
    created_at: datetime
