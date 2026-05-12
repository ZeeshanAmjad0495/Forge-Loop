from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SwarmType = Literal[
    "planning_review",
    "pr_review",
    "ci_failure_analysis",
    "incident_triage",
    "research",
    "architecture_review",
    "custom",
]


class SwarmPolicyCreate(BaseModel):
    name: str
    enabled: bool = True
    swarm_type: SwarmType = "custom"
    max_agents: int = 3
    max_tool_calls: int = 20
    max_estimated_cost_usd: float | None = None
    max_context_tokens_per_agent: int | None = None
    allowed_providers: list[str] = []
    requires_approval: bool = True
    default_model_route: str | None = None


class SwarmPolicyUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    swarm_type: SwarmType | None = None
    max_agents: int | None = None
    max_tool_calls: int | None = None
    max_estimated_cost_usd: float | None = None
    max_context_tokens_per_agent: int | None = None
    allowed_providers: list[str] | None = None
    requires_approval: bool | None = None
    default_model_route: str | None = None


class SwarmPolicy(BaseModel):
    id: str
    project_id: str
    name: str
    enabled: bool = True
    swarm_type: SwarmType = "custom"
    max_agents: int = 3
    max_tool_calls: int = 20
    max_estimated_cost_usd: float | None = None
    max_context_tokens_per_agent: int | None = None
    allowed_providers: list[str] = []
    requires_approval: bool = True
    default_model_route: str | None = None
    created_at: datetime
    updated_at: datetime


class SwarmBudgetCheckRequest(BaseModel):
    swarm_type: SwarmType = "custom"
    requested_agents: int = 1
    estimated_cost_usd: float = 0.0
    estimated_context_tokens_per_agent: int = 0
    providers: list[str] = []


class SwarmBudgetCheckResponse(BaseModel):
    allowed: bool
    warnings: list[str] = []
    blocking_errors: list[str] = []
    requires_approval: bool = False
    policy_id: str | None = None
    policy_name: str | None = None
    max_agents: int | None = None
    max_estimated_cost_usd: float | None = None
    allowed_providers: list[str] = []
