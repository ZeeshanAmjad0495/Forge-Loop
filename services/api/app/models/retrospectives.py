from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ProjectRetrospectiveStatus = Literal[
    "draft",
    "generated",
    "completed",
    "archived",
    "failed",
]


class ProjectRetrospectiveCreate(BaseModel):
    title: str
    trial_id: str | None = None
    status: ProjectRetrospectiveStatus = "draft"
    summary: str | None = None
    what_worked: list[str] = []
    what_failed: list[str] = []
    quality_notes: str | None = None
    cost_notes: str | None = None
    feedback_themes: list[str] = []
    failure_themes: list[str] = []
    decisions: list[str] = []
    recommendations: list[str] = []
    memory_candidate_ids: list[str] = []
    proposal_ids: list[str] = []
    provider: str | None = None
    model: str | None = None


class ProjectRetrospectiveUpdate(BaseModel):
    title: str | None = None
    status: ProjectRetrospectiveStatus | None = None
    summary: str | None = None
    what_worked: list[str] | None = None
    what_failed: list[str] | None = None
    quality_notes: str | None = None
    cost_notes: str | None = None
    feedback_themes: list[str] | None = None
    failure_themes: list[str] | None = None
    decisions: list[str] | None = None
    recommendations: list[str] | None = None
    memory_candidate_ids: list[str] | None = None
    proposal_ids: list[str] | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None


class ProjectRetrospectiveGenerateRequest(BaseModel):
    title: str | None = None
    summary_inputs: str = ""


class ProjectRetrospective(BaseModel):
    id: str
    project_id: str
    trial_id: str | None = None
    title: str
    status: ProjectRetrospectiveStatus = "draft"
    summary: str | None = None
    what_worked: list[str] = []
    what_failed: list[str] = []
    quality_notes: str | None = None
    cost_notes: str | None = None
    feedback_themes: list[str] = []
    failure_themes: list[str] = []
    decisions: list[str] = []
    recommendations: list[str] = []
    memory_candidate_ids: list[str] = []
    proposal_ids: list[str] = []
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
