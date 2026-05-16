from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Task 76: lifecycle of a provider-usage / cost record.
CostRecordStatus = Literal["planned", "completed", "failed", "blocked"]

CostRecordSourceType = Literal[
    "agent_run",
    "requirement_analysis",
    "task_decomposition",
    "tool_run",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
    "memory_learning",
    "artifact_summary",
    "context_pack",
    "model_route",
    "build_trial",
    "manual",
    "custom",
]

CostRecordWorkflowType = Literal[
    "analysis",
    "planning",
    "coding",
    "review",
    "qa",
    "ci",
    "incident",
    "memory",
    "compression",
    "research",
    "manual",
    "custom",
]


class CostRecordCreate(BaseModel):
    source_type: CostRecordSourceType
    source_id: str
    workflow_type: CostRecordWorkflowType
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_input_cost_usd: float = 0.0
    estimated_output_cost_usd: float = 0.0
    estimated_cached_input_cost_usd: float = 0.0
    currency: str = "USD"
    metadata: dict = {}
    # Task 76 audit fields (all optional; defaults preserve prior behavior).
    status: CostRecordStatus = "completed"
    selected_provider: str | None = None
    selected_model: str | None = None
    routing_reason: str | None = None
    fallback_chain: list[str] = []
    was_expensive_provider: bool = False
    required_approval: bool = False
    approval_id: str | None = None
    blocked_reason: str | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_cost_usd: float | None = None


class CostRecord(BaseModel):
    id: str
    project_id: str
    source_type: CostRecordSourceType
    source_id: str
    workflow_type: CostRecordWorkflowType
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0
    estimated_input_cost_usd: float = 0.0
    estimated_output_cost_usd: float = 0.0
    estimated_cached_input_cost_usd: float = 0.0
    estimated_total_cost_usd: float = 0.0
    currency: str = "USD"
    metadata: dict = {}
    # Task 76 audit fields.
    status: CostRecordStatus = "completed"
    selected_provider: str | None = None
    selected_model: str | None = None
    routing_reason: str | None = None
    fallback_chain: list[str] = []
    was_expensive_provider: bool = False
    required_approval: bool = False
    approval_id: str | None = None
    blocked_reason: str | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_cost_usd: float | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
