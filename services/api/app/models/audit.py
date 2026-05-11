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
