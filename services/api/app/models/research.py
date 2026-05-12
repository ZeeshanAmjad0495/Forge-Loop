from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ResearchBriefStatus = Literal[
    "draft",
    "requested",
    "completed",
    "failed",
    "archived",
]
ResearchBriefType = Literal[
    "tool_evaluation",
    "model_evaluation",
    "architecture",
    "cost_optimization",
    "quality_improvement",
    "security",
    "testing",
    "market",
    "paper_review",
    "custom",
]


class ResearchBriefCreate(BaseModel):
    title: str
    research_type: ResearchBriefType = "custom"
    question: str = ""
    scope: str = ""
    project_id: str | None = None
    summary: str | None = None
    findings: list[str] = []
    recommendations: list[str] = []
    risks: list[str] = []
    source_ids: list[str] = []
    provider: str | None = None
    model: str | None = None
    status: ResearchBriefStatus = "draft"


class ResearchBriefUpdate(BaseModel):
    title: str | None = None
    research_type: ResearchBriefType | None = None
    status: ResearchBriefStatus | None = None
    question: str | None = None
    scope: str | None = None
    summary: str | None = None
    findings: list[str] | None = None
    recommendations: list[str] | None = None
    risks: list[str] | None = None
    source_ids: list[str] | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None


class ResearchBriefGenerateRequest(BaseModel):
    title: str
    research_type: ResearchBriefType = "custom"
    question: str = ""
    scope: str = ""
    project_id: str | None = None
    source_ids: list[str] = []
    source_summaries: list[str] = []


class ResearchBrief(BaseModel):
    id: str
    project_id: str | None = None
    title: str
    research_type: ResearchBriefType = "custom"
    status: ResearchBriefStatus = "draft"
    question: str = ""
    scope: str = ""
    summary: str | None = None
    findings: list[str] = []
    recommendations: list[str] = []
    risks: list[str] = []
    source_ids: list[str] = []
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Task 64 — Research source cache
# ---------------------------------------------------------------------------

ResearchSourceType = Literal[
    "paper",
    "docs",
    "blog",
    "repo",
    "benchmark",
    "issue",
    "discussion",
    "internal_note",
    "custom",
]
ResearchSourceTrustLevel = Literal[
    "high",
    "medium",
    "low",
    "unknown",
]


class ResearchSourceCreate(BaseModel):
    title: str
    source_type: ResearchSourceType = "internal_note"
    project_id: str | None = None
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    accessed_at: datetime | None = None
    summary: str = ""
    key_points: list[str] = []
    relevance: str | None = None
    trust_level: ResearchSourceTrustLevel = "unknown"
    tags: list[str] = []
    cache_key: str | None = None


class ResearchSourceUpdate(BaseModel):
    title: str | None = None
    source_type: ResearchSourceType | None = None
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    accessed_at: datetime | None = None
    summary: str | None = None
    key_points: list[str] | None = None
    relevance: str | None = None
    trust_level: ResearchSourceTrustLevel | None = None
    tags: list[str] | None = None
    cache_key: str | None = None


class ResearchSource(BaseModel):
    id: str
    project_id: str | None = None
    title: str
    source_type: ResearchSourceType = "internal_note"
    url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    accessed_at: datetime | None = None
    summary: str = ""
    key_points: list[str] = []
    relevance: str | None = None
    trust_level: ResearchSourceTrustLevel = "unknown"
    tags: list[str] = []
    cache_key: str | None = None
    created_at: datetime
    updated_at: datetime
