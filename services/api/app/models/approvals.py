from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ApprovalTargetType = Literal[
    "requirement_analysis",
    "task_decomposition",
    "dev_task",
    "subtask",
    "artifact",
    "revision_work_item",
]
ApprovalStatus = Literal["pending", "approved", "rejected", "needs_revision"]


class ApprovalCreate(BaseModel):
    project_id: str
    target_type: ApprovalTargetType
    target_id: str
    feedback: str | None = None


class ApprovalUpdate(BaseModel):
    status: ApprovalStatus
    feedback: str | None = None


class Approval(BaseModel):
    id: str
    project_id: str
    target_type: ApprovalTargetType
    target_id: str
    status: ApprovalStatus
    requested_by: str
    decided_by: str | None = None
    feedback: str | None = None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
