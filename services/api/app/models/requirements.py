from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .agents import AgentRun
from .artifacts import Artifact

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


class RequirementGenerationRunCreate(BaseModel):
    provider: str | None = None


class RequirementGenerationResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact
    requirements: list[Requirement]
