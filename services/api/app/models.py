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
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_type: Literal["planning", "requirement_analysis"]
    provider: str
    model: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


class Artifact(BaseModel):
    id: str
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_run_id: str
    artifact_type: Literal["implementation_brief", "requirement_analysis"]
    content: str
    created_at: datetime


class PlanningRunResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact


class PlanningRunCreate(BaseModel):
    provider: str | None = None


class RequirementAnalysis(BaseModel):
    id: str
    project_id: str | None
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_run_id: str
    status: Literal["completed", "failed"]
    summary: str
    clarified_requirement: str
    assumptions: list[str]
    ambiguities: list[str]
    clarification_questions: list[str]
    risks: list[str]
    affected_areas: list[str]
    readiness: Literal["ready_for_planning", "needs_clarification"]
    created_at: datetime
    updated_at: datetime


class RequirementAnalysisRunCreate(BaseModel):
    provider: str | None = None


class RequirementAnalysisRunResponse(BaseModel):
    agent_run: AgentRun
    requirement_analysis: RequirementAnalysis
    artifact: Artifact


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


RequirementStatus = Literal["draft", "ready_for_analysis", "analyzed"]
RequirementSource = Literal["manual", "agent_generated", "imported"]


class RequirementCreate(BaseModel):
    title: str
    problem_statement: str = ""
    business_goal: str = ""
    target_users: list[str] = []
    functional_requirements: list[str] = []
    non_functional_requirements: list[str] = []
    acceptance_criteria: list[str] = []
    constraints: list[str] = []
    non_goals: list[str] = []
    assumptions: list[str] = []
    source: RequirementSource = "manual"
    status: RequirementStatus = "draft"


class RequirementUpdate(BaseModel):
    title: str
    problem_statement: str = ""
    business_goal: str = ""
    target_users: list[str] = []
    functional_requirements: list[str] = []
    non_functional_requirements: list[str] = []
    acceptance_criteria: list[str] = []
    constraints: list[str] = []
    non_goals: list[str] = []
    assumptions: list[str] = []
    status: RequirementStatus = "draft"


class Requirement(BaseModel):
    id: str
    project_id: str
    title: str
    problem_statement: str = ""
    business_goal: str = ""
    target_users: list[str] = []
    functional_requirements: list[str] = []
    non_functional_requirements: list[str] = []
    acceptance_criteria: list[str] = []
    constraints: list[str] = []
    non_goals: list[str] = []
    assumptions: list[str] = []
    source: RequirementSource = "manual"
    status: RequirementStatus = "draft"
    created_at: datetime
    updated_at: datetime
