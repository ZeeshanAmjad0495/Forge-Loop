from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str


class Ticket(BaseModel):
    id: str
    title: str
    description: str
    status: Literal["created", "brief_generated"]
    created_at: datetime
    updated_at: datetime


class AgentRun(BaseModel):
    id: str
    ticket_id: str
    agent_type: Literal["planning"]
    provider: str
    model: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


class Artifact(BaseModel):
    id: str
    ticket_id: str
    agent_run_id: str
    artifact_type: Literal["implementation_brief"]
    content: str
    created_at: datetime


class PlanningRunResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact


class PlanningRunCreate(BaseModel):
    provider: str | None = None


class ProviderInfo(BaseModel):
    name: str
    configured: bool
    default_model: str


class ProvidersResponse(BaseModel):
    default_provider: str
    providers: list[ProviderInfo]


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    email: str
