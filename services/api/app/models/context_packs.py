from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Task 78: how aggressively the pack was reduced to fit the token budget.
CompressionLevel = Literal["none", "light", "aggressive"]

ContextPackPurpose = Literal[
    "requirement_analysis",
    "task_decomposition",
    "coding_instruction",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
    "memory_learning",
    "artifact_summary",
    "research",
    "custom",
]


class ContextPackCreate(BaseModel):
    source_type: str
    source_id: str
    target_type: str | None = None
    target_id: str | None = None
    purpose: ContextPackPurpose
    provider: str = ""
    model: str = ""
    content_summary: str = ""
    included_memory_ids: list[str] = []
    included_artifact_ids: list[str] = []
    included_requirement_ids: list[str] = []
    included_task_ids: list[str] = []
    included_file_refs: list[str] = []
    rules_summary: str = ""
    safety_summary: str = ""
    estimated_tokens: int = 0
    actual_input_tokens: int = 0
    artifact_id: str | None = None
    metadata: dict = {}
    # Task 78 layered/compression fields (additive).
    compression_level: CompressionLevel = "none"
    excluded_context_reasoning: list[str] = []
    source_ids: list[str] = []


class ContextPack(BaseModel):
    id: str
    project_id: str
    source_type: str
    source_id: str
    target_type: str | None = None
    target_id: str | None = None
    purpose: ContextPackPurpose
    provider: str = ""
    model: str = ""
    content_summary: str = ""
    included_memory_ids: list[str] = []
    included_artifact_ids: list[str] = []
    included_requirement_ids: list[str] = []
    included_task_ids: list[str] = []
    included_file_refs: list[str] = []
    rules_summary: str = ""
    safety_summary: str = ""
    estimated_tokens: int = 0
    actual_input_tokens: int = 0
    artifact_id: str | None = None
    metadata: dict = {}
    compression_level: CompressionLevel = "none"
    excluded_context_reasoning: list[str] = []
    source_ids: list[str] = []
    created_at: datetime
    updated_at: datetime
