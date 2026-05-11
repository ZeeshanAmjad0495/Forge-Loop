from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .core import AssigneeType

EpicStatus = Literal["proposed", "ready", "in_progress", "blocked", "completed"]
EpicPriority = Literal["low", "medium", "high"]


class EpicCreate(BaseModel):
    requirement_id: str | None = None
    title: str
    description: str = ""
    priority: EpicPriority = "medium"
    sequence_order: int = 0
    acceptance_criteria: list[str] = []
    business_goal: str = ""
    assignee_type: AssigneeType = "unassigned"
    assignee_id: str | None = None
    assignee_name: str | None = None


class Epic(BaseModel):
    id: str
    project_id: str
    requirement_id: str | None = None
    title: str
    description: str = ""
    status: EpicStatus = "proposed"
    priority: EpicPriority = "medium"
    sequence_order: int = 0
    acceptance_criteria: list[str] = []
    business_goal: str = ""
    assignee_type: AssigneeType = "unassigned"
    assignee_id: str | None = None
    assignee_name: str | None = None
    created_at: datetime
    updated_at: datetime


class EpicUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: EpicStatus | None = None
    priority: EpicPriority | None = None
    sequence_order: int | None = None
    acceptance_criteria: list[str] | None = None
    business_goal: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None
