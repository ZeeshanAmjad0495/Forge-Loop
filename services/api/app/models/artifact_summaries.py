from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ArtifactSummaryType = Literal[
    "short",
    "structured",
    "agent_ready",
    "log",
    "diff",
    "test_output",
    "command_output",
    "tool_output",
    "custom",
]

ArtifactSummaryStatus = Literal["pending", "completed", "failed", "skipped"]


class ArtifactSummaryCreate(BaseModel):
    summary_type: ArtifactSummaryType = "short"
    provider: str | None = None
    model: str | None = None


class ArtifactSummary(BaseModel):
    id: str
    project_id: str | None = None
    artifact_id: str
    summary_type: ArtifactSummaryType
    status: ArtifactSummaryStatus = "completed"
    provider: str = "fallback"
    model: str = "deterministic"
    short_summary: str = ""
    structured_summary: dict = {}
    agent_ready_summary: str = ""
    source_size_bytes: int = 0
    summary_size_bytes: int = 0
    compression_ratio: float = 0.0
    error_message: str | None = None
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
