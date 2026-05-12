from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ProjectBuildTrialStatus = Literal[
    "planned",
    "running",
    "completed",
    "failed",
    "cancelled",
]
ProjectBuildTrialVerdict = Literal[
    "pass",
    "pass_with_manual_fallback",
    "fail",
    "inconclusive",
    "not_evaluated",
]
ProjectBuildTrialType = Literal[
    "execution_bridge",
    "real_project",
    "benchmark",
    "regression",
    "manual",
]

ProjectBuildTrialStageType = Literal[
    "setup",
    "requirement",
    "planning",
    "approval",
    "workspace",
    "branch",
    "command",
    "check",
    "tool_execution",
    "commit",
    "pr_draft",
    "github_pr",
    "review",
    "feedback",
    "revision",
    "memory",
    "final_verification",
    "custom",
]
ProjectBuildTrialStageStatus = Literal[
    "pending",
    "running",
    "passed",
    "failed",
    "skipped",
    "manual_fallback",
    "blocked",
]


class ProjectBuildTrialCreate(BaseModel):
    name: str
    goal: str = ""
    trial_type: ProjectBuildTrialType = "manual"
    repository_id: str | None = None
    workspace_id: str | None = None
    requirement_id: str | None = None
    pr_draft_id: str | None = None
    summary: str | None = None


class ProjectBuildTrialUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    status: ProjectBuildTrialStatus | None = None
    verdict: ProjectBuildTrialVerdict | None = None
    trial_type: ProjectBuildTrialType | None = None
    repository_id: str | None = None
    workspace_id: str | None = None
    requirement_id: str | None = None
    pr_draft_id: str | None = None
    summary: str | None = None
    lessons_learned: str | None = None


class ProjectBuildTrialComplete(BaseModel):
    verdict: ProjectBuildTrialVerdict = "not_evaluated"
    summary: str | None = None
    lessons_learned: str | None = None


class ProjectBuildTrial(BaseModel):
    id: str
    project_id: str
    name: str
    goal: str = ""
    status: ProjectBuildTrialStatus = "planned"
    verdict: ProjectBuildTrialVerdict = "not_evaluated"
    trial_type: ProjectBuildTrialType = "manual"
    repository_id: str | None = None
    workspace_id: str | None = None
    requirement_id: str | None = None
    pr_draft_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: str | None = None
    lessons_learned: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectBuildTrialStageCreate(BaseModel):
    name: str
    stage_type: ProjectBuildTrialStageType = "custom"
    status: ProjectBuildTrialStageStatus = "pending"
    evidence_summary: str | None = None
    linked_artifact_id: str | None = None
    linked_check_run_id: str | None = None
    linked_command_run_id: str | None = None
    linked_tool_run_id: str | None = None
    linked_pr_review_id: str | None = None
    linked_feedback_id: str | None = None
    notes: str | None = None


class ProjectBuildTrialStageUpdate(BaseModel):
    name: str | None = None
    stage_type: ProjectBuildTrialStageType | None = None
    status: ProjectBuildTrialStageStatus | None = None
    evidence_summary: str | None = None
    linked_artifact_id: str | None = None
    linked_check_run_id: str | None = None
    linked_command_run_id: str | None = None
    linked_tool_run_id: str | None = None
    linked_pr_review_id: str | None = None
    linked_feedback_id: str | None = None
    notes: str | None = None


class ProjectBuildTrialStage(BaseModel):
    id: str
    project_id: str
    trial_id: str
    name: str
    stage_type: ProjectBuildTrialStageType = "custom"
    status: ProjectBuildTrialStageStatus = "pending"
    evidence_summary: str | None = None
    linked_artifact_id: str | None = None
    linked_check_run_id: str | None = None
    linked_command_run_id: str | None = None
    linked_tool_run_id: str | None = None
    linked_pr_review_id: str | None = None
    linked_feedback_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectBuildTrialSummary(BaseModel):
    trial: ProjectBuildTrial
    stage_counts: dict[str, int]
    total_stages: int
