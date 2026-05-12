from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ArchitectureReviewTargetType = Literal[
    "project",
    "repository",
    "requirement",
    "dev_task",
    "build_trial",
    "forge_loop",
    "custom",
]
ArchitectureReviewStatus = Literal[
    "requested",
    "completed",
    "failed",
    "archived",
]


class ArchitectureReviewCreate(BaseModel):
    title: str
    target_type: ArchitectureReviewTargetType = "project"
    target_id: str | None = None
    project_id: str | None = None
    scope: str = ""
    status: ArchitectureReviewStatus = "requested"
    summary: str | None = None
    findings: list[str] = []
    recommendations: list[str] = []
    risks: list[str] = []
    score: float | None = None
    provider: str | None = None
    model: str | None = None


class ArchitectureReviewUpdate(BaseModel):
    title: str | None = None
    target_type: ArchitectureReviewTargetType | None = None
    target_id: str | None = None
    status: ArchitectureReviewStatus | None = None
    scope: str | None = None
    summary: str | None = None
    findings: list[str] | None = None
    recommendations: list[str] | None = None
    risks: list[str] | None = None
    score: float | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None


class ArchitectureReviewGenerateRequest(BaseModel):
    title: str
    target_type: ArchitectureReviewTargetType = "project"
    target_id: str | None = None
    project_id: str | None = None
    scope: str = ""
    context: str = ""


class ArchitectureReview(BaseModel):
    id: str
    project_id: str | None = None
    target_type: ArchitectureReviewTargetType = "project"
    target_id: str | None = None
    title: str
    scope: str = ""
    status: ArchitectureReviewStatus = "requested"
    summary: str | None = None
    findings: list[str] = []
    recommendations: list[str] = []
    risks: list[str] = []
    score: float | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
