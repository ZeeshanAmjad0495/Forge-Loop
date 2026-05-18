from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from .agents import AgentRun
from .artifacts import Artifact

RequirementStatus = Literal["draft", "ready_for_analysis", "analyzed"]
RequirementSource = Literal["manual", "agent_generated", "imported"]

_REQ_LIST_FIELDS = (
    "target_users",
    "functional_requirements",
    "non_functional_requirements",
    "acceptance_criteria",
    "constraints",
    "non_goals",
    "assumptions",
)


class _ReqListCoercion(BaseModel):
    # B6: these are list[str], but callers naturally send a bare string for
    # a single value (e.g. target_users="developers"). Accept both: a
    # non-empty string becomes a 1-element list; None/"" becomes [].
    @field_validator(*_REQ_LIST_FIELDS, mode="before", check_fields=False)
    @classmethod
    def _coerce_str_to_list(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v


class RequirementCreate(_ReqListCoercion):
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


class RequirementUpdate(_ReqListCoercion):
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
    expensive_approved: bool = False


class RequirementAnalysisRunResponse(BaseModel):
    agent_run: AgentRun
    requirement_analysis: RequirementAnalysis
    artifact: Artifact


class RequirementGenerationRunCreate(BaseModel):
    provider: str | None = None
    expensive_approved: bool = False


class RequirementGenerationResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact
    requirements: list[Requirement]
