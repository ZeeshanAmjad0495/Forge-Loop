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
        "tool_run_result",
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
    "tool_runner_definition_created",
    "tool_runner_definition_updated",
    "tool_run_recorded",
    "openhands_package_prepared",
    "openhands_result_recorded",
    "pr_draft_prepared",
    "pr_draft_updated",
    "pr_draft_approved",
    "pr_review_requested",
    "pr_review_recorded",
    "pr_review_completed",
    "ci_event_recorded",
    "ci_analysis_requested",
    "ci_analysis_completed",
    "ci_analysis_failed",
    "incident_recorded",
    "incident_updated",
    "incident_analysis_requested",
    "incident_analysis_completed",
    "incident_analysis_failed",
    "remediation_work_item_prepared",
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


# ---------------------------------------------------------------------------
# Tool runner definitions and tool runs (Task 26)
# ---------------------------------------------------------------------------

RunnerType = Literal[
    "openhands",
    "aider",
    "cline",
    "opencode",
    "hermes",
    "openclaw",
    "manual",
    "custom",
]
ToolRunnerMode = Literal["local", "api", "manual", "dry_run"]
ToolRunTargetType = Literal[
    "requirement",
    "epic",
    "dev_task",
    "subtask",
    "check_run",
    "manual",
]
ToolRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ToolRunConclusion = Literal[
    "success",
    "failure",
    "neutral",
    "skipped",
    "requires_human_action",
]


class ToolRunnerDefinitionCreate(BaseModel):
    code_repository_id: str | None = None
    name: str
    runner_type: RunnerType
    enabled: bool = True
    mode: ToolRunnerMode = "dry_run"
    description: str = ""
    config: dict = {}


class ToolRunnerDefinitionUpdate(BaseModel):
    name: str | None = None
    runner_type: RunnerType | None = None
    enabled: bool | None = None
    mode: ToolRunnerMode | None = None
    description: str | None = None
    config: dict | None = None


class ToolRunnerDefinition(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    name: str
    runner_type: RunnerType
    enabled: bool = True
    mode: ToolRunnerMode = "dry_run"
    description: str = ""
    config: dict = {}
    created_at: datetime
    updated_at: datetime


class ToolRunnerDefinitionsDefaultsRequest(BaseModel):
    code_repository_id: str | None = None


class ToolRunnerDefinitionsDefaultsResponse(BaseModel):
    created: list[ToolRunnerDefinition]
    existing: list[ToolRunnerDefinition]


class ToolRunCreate(BaseModel):
    project_id: str
    code_repository_id: str | None = None
    tool_runner_definition_id: str | None = None
    target_type: ToolRunTargetType
    target_id: str
    runner_type: RunnerType
    mode: ToolRunnerMode
    status: ToolRunStatus = "completed"
    conclusion: ToolRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ToolRun(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    tool_runner_definition_id: str | None = None
    target_type: ToolRunTargetType
    target_id: str
    runner_type: RunnerType
    mode: ToolRunnerMode
    status: ToolRunStatus
    conclusion: ToolRunConclusion | None = None
    summary: str = ""
    output: str | None = None
    artifact_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# OpenHandsRunner integration foundation (Task 27)
# ---------------------------------------------------------------------------

class OpenHandsPreparePackageRequest(BaseModel):
    tool_runner_definition_id: str | None = None
    code_repository_id: str | None = None


class OpenHandsInstructionPackage(BaseModel):
    schema_version: str = "1"
    runner: Literal["openhands"] = "openhands"
    mode: Literal["dry_run"] = "dry_run"
    project: dict
    repository: dict | None = None
    dev_task: dict
    context: dict
    safety: dict | None = None
    instructions: list[str]


class OpenHandsPrepareResponse(BaseModel):
    tool_run: ToolRun
    instruction_package: OpenHandsInstructionPackage


class OpenHandsRecordResultRequest(BaseModel):
    summary: str = ""
    output: str = ""
    conclusion: ToolRunConclusion = "neutral"


# ---------------------------------------------------------------------------
# PR draft workflow (Task 28)
# ---------------------------------------------------------------------------

PullRequestDraftStatus = Literal[
    "draft_prepared",
    "awaiting_approval",
    "approved_for_creation",
    "created",
    "failed",
    "closed",
    "cancelled",
]
# 'github' is reserved for forward compatibility; current build rejects it.
PullRequestDraftProvider = Literal["manual", "local", "github"]


class PullRequestDraftCreate(BaseModel):
    code_repository_id: str
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    title: str | None = None
    body: str | None = None
    source_branch: str | None = None
    target_branch: str = "main"
    provider: PullRequestDraftProvider = "manual"


class PullRequestDraftUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    status: PullRequestDraftStatus | None = None
    external_pr_url: str | None = None
    external_pr_number: int | None = None
    error_message: str | None = None


class PullRequestDraft(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    dev_task_id: str | None = None
    subtask_id: str | None = None
    tool_run_id: str | None = None
    title: str
    body: str
    source_branch: str
    target_branch: str = "main"
    status: PullRequestDraftStatus = "draft_prepared"
    provider: PullRequestDraftProvider = "manual"
    external_pr_url: str | None = None
    external_pr_number: int | None = None
    created_by: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None


# ---------------------------------------------------------------------------
# PR review integration foundation (Task 29)
# ---------------------------------------------------------------------------

PullRequestReviewProvider = Literal["kody", "manual", "custom"]
PullRequestReviewStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]
PullRequestReviewConclusion = Literal[
    "approved",
    "changes_requested",
    "comment_only",
    "failed",
    "skipped",
    "requires_human_review",
]
PullRequestReviewFindingSeverity = Literal["blocking", "warning", "info"]
PullRequestReviewFindingCategory = Literal[
    "security",
    "tests",
    "correctness",
    "maintainability",
    "performance",
    "scope",
    "style",
]


class PullRequestReviewFinding(BaseModel):
    severity: PullRequestReviewFindingSeverity | None = None
    category: PullRequestReviewFindingCategory | None = None
    message: str
    file_path: str | None = None
    line: int | None = None
    recommendation: str | None = None


class PullRequestReviewCreate(BaseModel):
    provider: PullRequestReviewProvider = "kody"
    mode: Literal["manual", "prepare"] = "prepare"
    summary: str | None = None
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None
    conclusion: PullRequestReviewConclusion | None = None
    external_review_url: str | None = None


class PullRequestReviewUpdate(BaseModel):
    status: PullRequestReviewStatus | None = None
    conclusion: PullRequestReviewConclusion | None = None
    summary: str | None = None
    findings: list[PullRequestReviewFinding] | None = None
    recommendations: str | None = None
    raw_output: str | None = None
    external_review_url: str | None = None
    error_message: str | None = None


class PullRequestReviewComplete(BaseModel):
    conclusion: PullRequestReviewConclusion
    summary: str | None = None
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None


class PullRequestReview(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    pr_draft_id: str
    provider: PullRequestReviewProvider
    status: PullRequestReviewStatus
    conclusion: PullRequestReviewConclusion | None = None
    summary: str = ""
    findings: list[PullRequestReviewFinding] = []
    recommendations: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    external_review_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


# ---------------------------------------------------------------------------
# CI failure ingestion and analysis (Task 30)
# ---------------------------------------------------------------------------

CIEventProvider = Literal[
    "github_actions",
    "gitlab_ci",
    "circleci",
    "manual",
    "custom",
]
CIEventStatus = Literal["queued", "in_progress", "completed", "failed"]
CIEventConclusion = Literal[
    "success",
    "failure",
    "cancelled",
    "skipped",
    "timed_out",
    "neutral",
    "unknown",
]


class CIEventCreate(BaseModel):
    code_repository_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    check_run_id: str | None = None
    provider: CIEventProvider
    external_run_id: str | None = None
    workflow_name: str | None = None
    job_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    status: CIEventStatus
    conclusion: CIEventConclusion
    failure_summary: str | None = None
    logs_excerpt: str | None = None
    raw_payload: dict | None = None


class CIEvent(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    check_run_id: str | None = None
    provider: CIEventProvider
    external_run_id: str | None = None
    workflow_name: str | None = None
    job_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    status: CIEventStatus
    conclusion: CIEventConclusion
    failure_summary: str | None = None
    logs_excerpt: str | None = None
    raw_payload: dict | None = None
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime


CIAnalysisStatus = Literal["pending", "running", "completed", "failed"]
CIAnalysisConclusion = Literal[
    "flaky_test",
    "code_regression",
    "dependency_issue",
    "configuration_issue",
    "infrastructure_issue",
    "unknown",
    "needs_human_review",
]


class CIAnalysisCreate(BaseModel):
    provider: str | None = None


class CIAnalysis(BaseModel):
    id: str
    project_id: str
    ci_event_id: str
    provider: str
    model: str
    status: CIAnalysisStatus
    conclusion: CIAnalysisConclusion | None = None
    summary: str = ""
    likely_root_causes: list[str] = []
    suggested_fixes: list[str] = []
    affected_areas: list[str] = []
    recommended_next_action: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Production / incident ticket workflow (Task 31)
# ---------------------------------------------------------------------------

IncidentSeverity = Literal["sev1", "sev2", "sev3", "sev4", "unknown"]
IncidentStatus = Literal[
    "reported",
    "triaging",
    "remediation_planned",
    "remediation_approved",
    "resolved",
    "closed",
    "cancelled",
]
IncidentSource = Literal[
    "manual",
    "ci_failure",
    "production_log",
    "monitoring",
    "user_report",
    "support",
    "custom",
]


class IncidentCreate(BaseModel):
    code_repository_id: str | None = None
    ci_event_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    title: str
    description: str
    severity: IncidentSeverity = "unknown"
    source: IncidentSource = "manual"
    environment: str | None = None
    affected_area: str | None = None
    started_at: datetime | None = None
    detected_at: datetime | None = None
    external_url: str | None = None
    evidence: str | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    source: IncidentSource | None = None
    environment: str | None = None
    affected_area: str | None = None
    evidence: str | None = None
    external_url: str | None = None
    resolved_at: datetime | None = None


class Incident(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    ci_event_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    title: str
    description: str
    severity: IncidentSeverity = "unknown"
    status: IncidentStatus = "reported"
    source: IncidentSource = "manual"
    environment: str | None = None
    affected_area: str | None = None
    started_at: datetime | None = None
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    external_url: str | None = None
    evidence: str | None = None
    created_at: datetime
    updated_at: datetime


IncidentAnalysisStatus = Literal["pending", "running", "completed", "failed"]
IncidentAnalysisConclusion = Literal[
    "code_regression",
    "configuration_issue",
    "infrastructure_issue",
    "dependency_issue",
    "data_issue",
    "security_issue",
    "flaky_external_service",
    "unknown",
    "needs_human_review",
]


class IncidentAnalysisCreate(BaseModel):
    provider: str | None = None


class IncidentAnalysis(BaseModel):
    id: str
    project_id: str
    incident_id: str
    provider: str
    model: str
    status: IncidentAnalysisStatus
    conclusion: IncidentAnalysisConclusion | None = None
    summary: str = ""
    impact_assessment: str | None = None
    likely_root_causes: list[str] = []
    immediate_actions: list[str] = []
    remediation_plan: list[str] = []
    prevention_actions: list[str] = []
    affected_areas: list[str] = []
    recommended_next_action: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class RemediationWorkItemDraft(BaseModel):
    """Non-persisted draft of a remediation DevTask suggestion.

    Returned by ``POST /incidents/{id}/prepare-remediation`` so a human can
    create a DevTask manually after review. ForgeLoop never auto-creates a
    coding-runner work item from an incident.
    """

    incident_id: str
    project_id: str
    analysis_id: str | None = None
    title: str
    description: str
    suggested_acceptance_criteria: list[str] = []
    requires_human_approval: bool = True
    created_at: datetime
