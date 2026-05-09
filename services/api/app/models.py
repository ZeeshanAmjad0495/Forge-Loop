from datetime import datetime
from typing import Literal
from pydantic import BaseModel

AssigneeType = Literal["human", "agent", "unassigned"]


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


class Artifact(BaseModel):
    id: str
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_run_id: str
    artifact_type: Literal[
        "implementation_brief",
        "requirement_analysis",
        "task_decomposition",
        "requirement_generation",
        "check_result",
    ]
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


class RequirementGenerationRunCreate(BaseModel):
    provider: str | None = None


class RequirementGenerationResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact
    requirements: list[Requirement]


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


DevTaskType = Literal[
    "backend", "frontend", "full_stack", "testing",
    "documentation", "infrastructure", "refactor", "unknown",
]
DevTaskStatus = Literal["proposed", "ready", "in_progress", "blocked", "completed"]
DevTaskPriority = Literal["low", "medium", "high"]


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


SubtaskStatus = Literal["proposed", "ready", "in_progress", "blocked", "completed"]


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


class TaskDecompositionResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact
    dev_tasks: list[DevTask]
    subtasks: list[Subtask]


class DevTaskWithSubtasksResponse(BaseModel):
    dev_task: DevTaskWithReadiness
    subtasks: list[Subtask]


ApprovalTargetType = Literal[
    "requirement_analysis", "task_decomposition", "dev_task", "subtask", "artifact"
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


AuditActorType = Literal["user", "system", "agent"]
AuditAction = Literal[
    "requirement_created",
    "requirement_analyzed",
    "task_decomposition_created",
    "dev_task_updated",
    "dev_task_assigned",
    "subtask_updated",
    "subtask_assigned",
    "approval_requested",
    "approval_approved",
    "approval_rejected",
    "approval_needs_revision",
    "change_requested",
    "code_repository_created",
    "code_repository_updated",
    "repo_safety_profile_updated",
    "requirement_generation_created",
    "epic_created",
    "epic_updated",
    "check_definition_created",
    "check_definition_updated",
    "check_run_recorded",
]


class AuditEvent(BaseModel):
    id: str
    project_id: str | None = None
    actor_type: AuditActorType
    actor_id: str
    action: AuditAction
    target_type: str
    target_id: str
    details: dict = {}
    created_at: datetime


CodeRepositoryProvider = Literal["github", "gitlab", "bitbucket", "other"]
CodeRepositoryStatus = Literal["active", "disabled"]


class CodeRepositoryCreate(BaseModel):
    provider: CodeRepositoryProvider = "github"
    repo_url: str
    name: str
    default_branch: str = "main"


class CodeRepositoryUpdate(BaseModel):
    provider: CodeRepositoryProvider | None = None
    repo_url: str | None = None
    name: str | None = None
    default_branch: str | None = None
    status: CodeRepositoryStatus | None = None


class CodeRepository(BaseModel):
    id: str
    project_id: str
    provider: CodeRepositoryProvider
    repo_url: str
    name: str
    default_branch: str
    status: CodeRepositoryStatus = "active"
    created_at: datetime
    updated_at: datetime


class RepoSafetyProfileUpsert(BaseModel):
    work_safe_mode: bool = True
    allowed_actions: list[str] = []
    blocked_paths: list[str] = []
    required_checks: list[str] = []
    requires_approval_for: list[str] = []
    protected_branches: list[str] = []
    notes: str = ""


class RepoSafetyProfile(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    work_safe_mode: bool
    allowed_actions: list[str]
    blocked_paths: list[str]
    required_checks: list[str]
    requires_approval_for: list[str]
    protected_branches: list[str]
    notes: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Check definitions and check runs (Task 25)
# ---------------------------------------------------------------------------

CheckType = Literal[
    "tests",
    "build",
    "lint",
    "typecheck",
    "coverage",
    "security_sast",
    "dependency_scan",
    "secret_scan",
    "container_scan",
    "accessibility",
    "e2e",
    "custom",
]
CheckSeverity = Literal["info", "warning", "blocking"]
CheckRunTargetType = Literal[
    "project",
    "requirement",
    "epic",
    "dev_task",
    "subtask",
    "pull_request",
    "manual",
]
CheckRunStatus = Literal["pending", "running", "completed", "failed"]
CheckRunConclusion = Literal["success", "failure", "neutral", "skipped", "cancelled"]


class CheckDefinitionCreate(BaseModel):
    code_repository_id: str | None = None
    name: str
    check_type: CheckType
    command: str = ""
    required: bool = True
    enabled: bool = True
    severity: CheckSeverity = "blocking"
    description: str = ""


class CheckDefinitionUpdate(BaseModel):
    name: str | None = None
    check_type: CheckType | None = None
    command: str | None = None
    required: bool | None = None
    enabled: bool | None = None
    severity: CheckSeverity | None = None
    description: str | None = None


class CheckDefinition(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    name: str
    check_type: CheckType
    command: str = ""
    required: bool = True
    enabled: bool = True
    severity: CheckSeverity = "blocking"
    description: str = ""
    created_at: datetime
    updated_at: datetime


class CheckDefinitionsFromSafetyProfileRequest(BaseModel):
    code_repository_id: str | None = None


class CheckRunCreate(BaseModel):
    project_id: str
    code_repository_id: str | None = None
    check_definition_id: str | None = None
    target_type: CheckRunTargetType
    target_id: str
    status: CheckRunStatus = "completed"
    conclusion: CheckRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CheckRun(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    check_definition_id: str | None = None
    target_type: CheckRunTargetType
    target_id: str
    status: CheckRunStatus
    conclusion: CheckRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    artifact_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CheckDefinitionsFromSafetyProfileResponse(BaseModel):
    created: list[CheckDefinition]
    existing: list[CheckDefinition]
