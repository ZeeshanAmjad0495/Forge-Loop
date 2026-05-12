from datetime import datetime
from typing import Literal

from pydantic import BaseModel

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
    created_at: datetime
    updated_at: datetime
