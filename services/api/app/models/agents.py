from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AgentRun(BaseModel):
    id: str
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_type: Literal[
        "planning",
        "requirement_analysis",
        "task_decomposition",
        "requirement_generation",
    ]
    provider: str
    model: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
