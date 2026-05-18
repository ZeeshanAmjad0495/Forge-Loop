from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MemoryCandidateSourceType = Literal[
    "manual",
    "approval",
    "audit_event",
    "check_run",
    "tool_run",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
    "dev_task",
    "subtask",
    "requirement",
    "artifact",
]
MemoryCandidateMemoryType = Literal[
    "architecture_decision",
    "project_rule",
    "coding_standard",
    "testing_rule",
    "deployment_rule",
    "approved_approach",
    "rejected_approach",
    "known_risk",
    "known_failure_pattern",
    "human_feedback",
    "important_file",
    "prompt_note",
    "qa_learning",
    "incident_learning",
    "cost_note",
    "custom",
]
MemoryCandidateStatus = Literal["proposed", "approved", "rejected", "superseded"]
MemoryLearningRunStatus = Literal["pending", "running", "completed", "failed"]


class ProjectMemoryCandidateCreate(BaseModel):
    source_type: MemoryCandidateSourceType = "manual"
    source_id: str | None = None
    memory_type: MemoryCandidateMemoryType
    title: str
    content: str
    tags: list[str] = []
    confidence: float | None = None
    proposed_by: str | None = None
    provider: str | None = None
    model: str | None = None
    learning_run_id: str | None = None


class ProjectMemoryCandidateUpdate(BaseModel):
    memory_type: MemoryCandidateMemoryType | None = None
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    confidence: float | None = None


class MemoryCandidateRejectRequest(BaseModel):
    reason: str | None = None


class ProjectMemoryCandidate(BaseModel):
    id: str
    project_id: str
    learning_run_id: str | None = None
    source_type: MemoryCandidateSourceType
    source_id: str | None = None
    memory_type: MemoryCandidateMemoryType
    title: str
    content: str
    tags: list[str] = []
    confidence: float | None = None
    status: MemoryCandidateStatus = "proposed"
    proposed_by: str | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None


class MemoryLearningRunCreate(BaseModel):
    source_type: MemoryCandidateSourceType
    source_id: str
    provider: str | None = None
    expensive_approved: bool = False


class MemoryLearningRun(BaseModel):
    id: str
    project_id: str
    source_type: MemoryCandidateSourceType
    source_id: str
    provider: str
    model: str
    status: MemoryLearningRunStatus
    summary: str = ""
    candidates_created: int = 0
    candidate_ids: list[str] = []
    artifact_id: str | None = None
    raw_output: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
