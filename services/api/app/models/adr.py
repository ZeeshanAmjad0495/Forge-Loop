from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ADRStatus = Literal[
    "proposed",
    "accepted",
    "rejected",
    "deprecated",
    "superseded",
]


class ArchitectureDecisionRecordCreate(BaseModel):
    title: str
    project_id: str | None = None
    proposal_id: str | None = None
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives_considered: list[str] = []
    related_source_ids: list[str] = []
    related_brief_ids: list[str] = []
    related_review_ids: list[str] = []
    tags: list[str] = []


class ArchitectureDecisionRecordUpdate(BaseModel):
    title: str | None = None
    proposal_id: str | None = None
    context: str | None = None
    decision: str | None = None
    consequences: str | None = None
    alternatives_considered: list[str] | None = None
    related_source_ids: list[str] | None = None
    related_brief_ids: list[str] | None = None
    related_review_ids: list[str] | None = None
    tags: list[str] | None = None


class ArchitectureDecisionSupersedeRequest(BaseModel):
    superseded_by_id: str


class ArchitectureDecisionRecord(BaseModel):
    id: str
    project_id: str | None = None
    proposal_id: str | None = None
    title: str
    status: ADRStatus = "proposed"
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives_considered: list[str] = []
    related_source_ids: list[str] = []
    related_brief_ids: list[str] = []
    related_review_ids: list[str] = []
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
    superseded_by_id: str | None = None
