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


class ProjectCreate(BaseModel):
    name: str
    description: str
    repo_url: str | None = None
    tech_stack: list[str] = []


class Project(BaseModel):
    id: str
    name: str
    description: str
    repo_url: str | None = None
    tech_stack: list[str] = []
    status: Literal["active"] = "active"
    created_at: datetime
    updated_at: datetime


class ProjectContextUpdate(BaseModel):
    architecture_notes: str = ""
    coding_standards: str = ""
    test_commands: str = ""
    deployment_commands: str = ""
    domain_rules: str = ""
    safety_rules: str = ""


class ProjectContext(ProjectContextUpdate):
    project_id: str
    updated_at: datetime | None = None


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
