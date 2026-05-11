from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str
    project_id: str | None = None


class Ticket(BaseModel):
    id: str
    title: str
    description: str
    status: Literal["created", "brief_generated"]
    created_at: datetime
    updated_at: datetime
    project_id: str | None = None
