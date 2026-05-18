from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .agents import AgentRun
from .artifacts import Artifact
from .core import AssigneeType

DevTaskType = Literal[
    "backend", "frontend", "full_stack", "testing",
    "documentation", "infrastructure", "refactor", "unknown",
]
DevTaskStatus = Literal["proposed", "ready", "in_progress", "blocked", "completed"]
DevTaskPriority = Literal["low", "medium", "high"]
SubtaskStatus = Literal["proposed", "ready", "in_progress", "blocked", "completed"]


class DevTask(BaseModel):
    id: str
    project_id: str
    requirement_id: str | None = None
    ticket_id: str | None = None
    source_analysis_id: str | None = None
    agent_run_id: str
    epic_id: str | None = None
    title: str
    description: str
    task_type: DevTaskType = "unknown"
    status: DevTaskStatus = "proposed"
    priority: DevTaskPriority = "medium"
    sequence_order: int = 0
    depends_on: list[str] = []
    acceptance_criteria: list[str] = []
    definition_of_done: list[str] = []
    qa_required: bool = False
    suggested_agent_type: str | None = None
    assignee_type: AssigneeType = "unassigned"
    assignee_id: str | None = None
    assignee_name: str | None = None
    created_at: datetime
    updated_at: datetime


class Subtask(BaseModel):
    id: str
    dev_task_id: str
    project_id: str
    title: str
    description: str
    status: SubtaskStatus = "proposed"
    sequence_order: int = 0
    acceptance_criteria: list[str] = []
    qa_required: bool = False
    assignee_type: AssigneeType = "unassigned"
    assignee_id: str | None = None
    assignee_name: str | None = None
    created_at: datetime
    updated_at: datetime


class DevTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: DevTaskStatus | None = None
    priority: DevTaskPriority | None = None
    sequence_order: int | None = None
    depends_on: list[str] | None = None
    acceptance_criteria: list[str] | None = None
    definition_of_done: list[str] | None = None
    qa_required: bool | None = None
    suggested_agent_type: str | None = None
    epic_id: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None


class SubtaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: SubtaskStatus | None = None
    sequence_order: int | None = None
    acceptance_criteria: list[str] | None = None
    qa_required: bool | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None


class DevTaskWithReadiness(DevTask):
    is_ready: bool = True
    blocked_by: list[str] = []


class TaskDecompositionRunCreate(BaseModel):
    provider: str | None = None
    expensive_approved: bool = False


class TaskDecompositionResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact
    dev_tasks: list[DevTask]
    subtasks: list[Subtask]


class DevTaskWithSubtasksResponse(BaseModel):
    dev_task: DevTaskWithReadiness
    subtasks: list[Subtask]
