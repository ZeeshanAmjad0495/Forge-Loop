from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ImprovementProposalSourceType = Literal[
    "research_brief",
    "architecture_review",
    "retrospective",
    "manual",
    "custom",
]
ImprovementProposalType = Literal[
    "architecture_change",
    "cost_optimization",
    "quality_improvement",
    "security_hardening",
    "developer_experience",
    "local_runtime",
    "model_routing",
    "testing",
    "documentation",
    "custom",
]
ImprovementProposalStatus = Literal[
    "proposed",
    "approved",
    "rejected",
    "deferred",
    "implemented",
    "archived",
]
ImprovementProposalPriority = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class ImprovementProposalCreate(BaseModel):
    title: str
    description: str = ""
    proposal_type: ImprovementProposalType = "custom"
    project_id: str | None = None
    source_type: ImprovementProposalSourceType = "manual"
    source_id: str | None = None
    priority: ImprovementProposalPriority = "medium"
    expected_benefit: str = ""
    risk: str = ""
    implementation_notes: str = ""
    affected_areas: list[str] = []


class ImprovementProposalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    proposal_type: ImprovementProposalType | None = None
    priority: ImprovementProposalPriority | None = None
    expected_benefit: str | None = None
    risk: str | None = None
    implementation_notes: str | None = None
    affected_areas: list[str] | None = None
    approval_id: str | None = None


class ImprovementProposalRejectRequest(BaseModel):
    reason: str = ""


class ImprovementProposal(BaseModel):
    id: str
    project_id: str | None = None
    source_type: ImprovementProposalSourceType = "manual"
    source_id: str | None = None
    title: str
    description: str = ""
    proposal_type: ImprovementProposalType = "custom"
    status: ImprovementProposalStatus = "proposed"
    priority: ImprovementProposalPriority = "medium"
    expected_benefit: str = ""
    risk: str = ""
    implementation_notes: str = ""
    affected_areas: list[str] = []
    approval_id: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    implemented_at: datetime | None = None
