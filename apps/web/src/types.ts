export interface Ticket {
  id: string
  title: string
  description: string
  status: 'created' | 'brief_generated'
  created_at: string
  updated_at: string
  project_id: string | null
}

export interface ProjectCreate {
  name: string
  description: string
  repo_url?: string | null
  tech_stack?: string[]
}

export interface Project {
  id: string
  name: string
  description: string
  repo_url: string | null
  tech_stack: string[]
  status: 'active'
  created_at: string
  updated_at: string
}

export interface ProjectContext {
  project_id: string
  architecture_notes: string
  coding_standards: string
  test_commands: string
  deployment_commands: string
  domain_rules: string
  safety_rules: string
  updated_at: string | null
}

export interface AgentRun {
  id: string
  ticket_id: string | null
  requirement_id: string | null
  agent_type: 'planning' | 'requirement_analysis' | 'task_decomposition' | 'requirement_generation'
  provider: string
  model: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error_message: string | null
}

export interface Artifact {
  id: string
  ticket_id: string | null
  requirement_id: string | null
  agent_run_id: string
  artifact_type: 'implementation_brief' | 'requirement_analysis' | 'task_decomposition' | 'requirement_generation' | 'check_result' | 'tool_run_result'
  content: string
  created_at: string
}

export interface PlanningRunResponse {
  agent_run: AgentRun
  artifact: Artifact
}

export interface RequirementAnalysis {
  id: string
  project_id: string | null
  ticket_id: string | null
  requirement_id: string | null
  agent_run_id: string
  status: 'completed' | 'failed'
  summary: string
  clarified_requirement: string
  assumptions: string[]
  ambiguities: string[]
  clarification_questions: string[]
  risks: string[]
  affected_areas: string[]
  readiness: 'ready_for_planning' | 'needs_clarification'
  created_at: string
  updated_at: string
}

export interface RequirementAnalysisRunResponse {
  agent_run: AgentRun
  requirement_analysis: RequirementAnalysis
  artifact: Artifact
}

export interface ProviderInfo {
  name: string
  configured: boolean
  default_model: string
}

export interface ProvidersResponse {
  default_provider: string
  providers: ProviderInfo[]
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface MeResponse {
  email: string
}

export type RequirementStatus = 'draft' | 'ready_for_analysis' | 'analyzed'
export type RequirementSource = 'manual' | 'agent_generated' | 'imported'

export interface RequirementCreate {
  title: string
  problem_statement?: string
  business_goal?: string
  target_users?: string[]
  functional_requirements?: string[]
  non_functional_requirements?: string[]
  acceptance_criteria?: string[]
  constraints?: string[]
  non_goals?: string[]
  assumptions?: string[]
  source?: RequirementSource
  status?: RequirementStatus
}

export interface RequirementUpdate {
  title: string
  problem_statement: string
  business_goal: string
  target_users: string[]
  functional_requirements: string[]
  non_functional_requirements: string[]
  acceptance_criteria: string[]
  constraints: string[]
  non_goals: string[]
  assumptions: string[]
  status: RequirementStatus
}

export interface Requirement {
  id: string
  project_id: string
  title: string
  problem_statement: string
  business_goal: string
  target_users: string[]
  functional_requirements: string[]
  non_functional_requirements: string[]
  acceptance_criteria: string[]
  constraints: string[]
  non_goals: string[]
  assumptions: string[]
  source: RequirementSource
  status: RequirementStatus
  created_at: string
  updated_at: string
}

export type AssigneeType = 'human' | 'agent' | 'unassigned'
export type EpicStatus = 'proposed' | 'ready' | 'in_progress' | 'blocked' | 'completed'
export type EpicPriority = 'low' | 'medium' | 'high'

export interface EpicCreate {
  title: string
  requirement_id?: string | null
  description?: string
  priority?: EpicPriority
  sequence_order?: number
  acceptance_criteria?: string[]
  business_goal?: string
  assignee_type?: AssigneeType
  assignee_id?: string | null
  assignee_name?: string | null
}

export interface EpicUpdate {
  title?: string
  description?: string
  status?: EpicStatus
  priority?: EpicPriority
  sequence_order?: number
  acceptance_criteria?: string[]
  business_goal?: string
  assignee_type?: AssigneeType
  assignee_id?: string | null
  assignee_name?: string | null
}

export interface Epic {
  id: string
  project_id: string
  requirement_id: string | null
  title: string
  description: string
  status: EpicStatus
  priority: EpicPriority
  sequence_order: number
  acceptance_criteria: string[]
  business_goal: string
  assignee_type: AssigneeType
  assignee_id: string | null
  assignee_name: string | null
  created_at: string
  updated_at: string
}

export type DevTaskType =
  | 'backend' | 'frontend' | 'full_stack' | 'testing'
  | 'documentation' | 'infrastructure' | 'refactor' | 'unknown'
export type DevTaskStatus = 'proposed' | 'ready' | 'in_progress' | 'blocked' | 'completed'
export type DevTaskPriority = 'low' | 'medium' | 'high'

export interface DevTask {
  id: string
  project_id: string
  requirement_id: string | null
  ticket_id: string | null
  source_analysis_id: string | null
  agent_run_id: string
  epic_id: string | null
  title: string
  description: string
  task_type: DevTaskType
  status: DevTaskStatus
  priority: DevTaskPriority
  sequence_order: number
  depends_on: string[]
  acceptance_criteria: string[]
  definition_of_done: string[]
  qa_required: boolean
  suggested_agent_type: string | null
  assignee_type: AssigneeType
  assignee_id: string | null
  assignee_name: string | null
  created_at: string
  updated_at: string
  is_ready?: boolean
  blocked_by?: string[]
}

export interface DevTaskUpdate {
  title?: string
  description?: string
  status?: DevTaskStatus
  priority?: DevTaskPriority
  sequence_order?: number
  depends_on?: string[]
  acceptance_criteria?: string[]
  definition_of_done?: string[]
  qa_required?: boolean
  suggested_agent_type?: string | null
  epic_id?: string | null
  assignee_type?: AssigneeType
  assignee_id?: string | null
  assignee_name?: string | null
}

export interface SubtaskUpdate {
  title?: string
  description?: string
  status?: DevTaskStatus
  sequence_order?: number
  acceptance_criteria?: string[]
  qa_required?: boolean
  assignee_type?: AssigneeType
  assignee_id?: string | null
  assignee_name?: string | null
}

export interface Subtask {
  id: string
  dev_task_id: string
  project_id: string
  title: string
  description: string
  status: DevTaskStatus
  sequence_order: number
  acceptance_criteria: string[]
  qa_required: boolean
  assignee_type: AssigneeType
  assignee_id: string | null
  assignee_name: string | null
  created_at: string
  updated_at: string
}

export interface RequirementGenerationResponse {
  agent_run: AgentRun
  artifact: Artifact
  requirements: Requirement[]
}

export interface TaskDecompositionResponse {
  agent_run: AgentRun
  artifact: Artifact
  dev_tasks: DevTask[]
  subtasks: Subtask[]
}

export type ApprovalTargetType =
  | 'requirement_analysis' | 'task_decomposition' | 'dev_task' | 'subtask' | 'artifact'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'needs_revision'
export type AuditActorType = 'user' | 'system' | 'agent'

export interface ApprovalCreate {
  project_id: string
  target_type: ApprovalTargetType
  target_id: string
  feedback?: string | null
}

export interface ApprovalDecision {
  status: 'approved' | 'rejected' | 'needs_revision'
  feedback?: string | null
}

export interface Approval {
  id: string
  project_id: string
  target_type: ApprovalTargetType
  target_id: string
  status: ApprovalStatus
  requested_by: string
  decided_by: string | null
  feedback: string | null
  created_at: string
  updated_at: string
  decided_at: string | null
}

export interface AuditEvent {
  id: string
  project_id: string | null
  actor_type: AuditActorType
  actor_id: string
  action: string
  target_type: string
  target_id: string
  details: Record<string, unknown>
  created_at: string
}

export type CodeRepositoryProvider = 'github' | 'gitlab' | 'bitbucket' | 'other'
export type CodeRepositoryStatus = 'active' | 'disabled'

export interface CodeRepositoryCreate {
  provider?: CodeRepositoryProvider
  repo_url: string
  name: string
  default_branch?: string
}

export interface CodeRepositoryUpdate {
  provider?: CodeRepositoryProvider | null
  repo_url?: string | null
  name?: string | null
  default_branch?: string | null
  status?: CodeRepositoryStatus | null
}

export interface CodeRepository {
  id: string
  project_id: string
  provider: CodeRepositoryProvider
  repo_url: string
  name: string
  default_branch: string
  status: CodeRepositoryStatus
  created_at: string
  updated_at: string
}

export interface RepoSafetyProfileUpsert {
  work_safe_mode?: boolean
  allowed_actions?: string[]
  blocked_paths?: string[]
  required_checks?: string[]
  requires_approval_for?: string[]
  protected_branches?: string[]
  notes?: string
}

export interface RepoSafetyProfile {
  id: string
  project_id: string
  code_repository_id: string
  work_safe_mode: boolean
  allowed_actions: string[]
  blocked_paths: string[]
  required_checks: string[]
  requires_approval_for: string[]
  protected_branches: string[]
  notes: string
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Check definitions and check runs (Task 25)
// ---------------------------------------------------------------------------



export type CheckType =
  | 'tests' | 'build' | 'lint' | 'typecheck' | 'coverage'
  | 'security_sast' | 'dependency_scan' | 'secret_scan' | 'container_scan'
  | 'accessibility' | 'e2e' | 'custom'

export type CheckSeverity = 'info' | 'warning' | 'blocking'

export type CheckRunTargetType =
  | 'project' | 'requirement' | 'epic' | 'dev_task' | 'subtask' | 'pull_request' | 'manual'

export type CheckRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export type CheckRunConclusion = 'success' | 'failure' | 'neutral' | 'skipped' | 'cancelled'

export interface CheckDefinitionCreate {
  code_repository_id?: string | null
  name: string
  check_type: CheckType
  command?: string
  required?: boolean
  enabled?: boolean
  severity?: CheckSeverity
  description?: string
}

export interface CheckDefinitionUpdate {
  name?: string
  check_type?: CheckType
  command?: string
  required?: boolean
  enabled?: boolean
  severity?: CheckSeverity
  description?: string
}

export interface CheckDefinition {
  id: string
  project_id: string
  code_repository_id: string | null
  name: string
  check_type: CheckType
  command: string
  required: boolean
  enabled: boolean
  severity: CheckSeverity
  description: string
  created_at: string
  updated_at: string
}

export interface CheckDefinitionsFromSafetyProfileResponse {
  created: CheckDefinition[]
  existing: CheckDefinition[]
}

export interface CheckRunCreate {
  project_id: string
  code_repository_id?: string | null
  check_definition_id?: string | null
  target_type: CheckRunTargetType
  target_id: string
  status?: CheckRunStatus
  conclusion?: CheckRunConclusion | null
  summary?: string
  output?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export interface CheckRun {
  id: string
  project_id: string
  code_repository_id: string | null
  check_definition_id: string | null
  target_type: CheckRunTargetType
  target_id: string
  status: CheckRunStatus
  conclusion: CheckRunConclusion | null
  summary: string
  output: string | null
  artifact_id: string | null
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Tool runner definitions and tool runs (Task 26)
// ---------------------------------------------------------------------------

export type RunnerType =
  | 'openhands' | 'aider' | 'cline' | 'opencode' | 'hermes' | 'openclaw' | 'manual' | 'custom'

export type ToolRunnerMode = 'local' | 'api' | 'manual' | 'dry_run'

export type ToolRunTargetType =
  | 'requirement' | 'epic' | 'dev_task' | 'subtask' | 'check_run' | 'manual'

export type ToolRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type ToolRunConclusion =
  | 'success' | 'failure' | 'neutral' | 'skipped' | 'requires_human_action'

export interface ToolRunnerDefinitionCreate {
  code_repository_id?: string | null
  name: string
  runner_type: RunnerType
  enabled?: boolean
  mode?: ToolRunnerMode
  description?: string
  config?: Record<string, unknown>
}

export interface ToolRunnerDefinitionUpdate {
  name?: string
  runner_type?: RunnerType
  enabled?: boolean
  mode?: ToolRunnerMode
  description?: string
  config?: Record<string, unknown>
}

export interface ToolRunnerDefinition {
  id: string
  project_id: string
  code_repository_id: string | null
  name: string
  runner_type: RunnerType
  enabled: boolean
  mode: ToolRunnerMode
  description: string
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ToolRunnerDefinitionsDefaultsResponse {
  created: ToolRunnerDefinition[]
  existing: ToolRunnerDefinition[]
}

export interface ToolRunCreate {
  project_id: string
  code_repository_id?: string | null
  tool_runner_definition_id?: string | null
  target_type: ToolRunTargetType
  target_id: string
  runner_type: RunnerType
  mode: ToolRunnerMode
  status?: ToolRunStatus
  conclusion?: ToolRunConclusion | null
  summary?: string
  output?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export interface ToolRun {
  id: string
  project_id: string
  code_repository_id: string | null
  tool_runner_definition_id: string | null
  target_type: ToolRunTargetType
  target_id: string
  runner_type: RunnerType
  mode: ToolRunnerMode
  status: ToolRunStatus
  conclusion: ToolRunConclusion | null
  summary: string
  output: string | null
  artifact_id: string | null
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// OpenHandsRunner (Task 27)
// ---------------------------------------------------------------------------

export interface OpenHandsInstructionPackage {
  schema_version: string
  runner: 'openhands'
  mode: 'dry_run'
  project: { id: string; name: string; tech_stack: string[] }
  repository: {
    id: string
    repo_url: string
    default_branch: string
    provider: string
  } | null
  dev_task: {
    id: string
    title: string
    description: string
    task_type: string
    acceptance_criteria: string[]
    definition_of_done: string[]
    requirement_id: string | null
    epic_id: string | null
  }
  context: {
    requirement_summary: string | null
    epic_title: string | null
    project_memory_summary: string | null
  }
  safety: {
    work_safe_mode: boolean
    allowed_actions: string[]
    blocked_paths: string[]
    required_checks: string[]
    requires_approval_for: string[]
    protected_branches: string[]
  } | null
  instructions: string[]
}

export interface OpenHandsPreparePackageRequest {
  tool_runner_definition_id?: string | null
  code_repository_id?: string | null
}

export interface OpenHandsPrepareResponse {
  tool_run: ToolRun
  instruction_package: OpenHandsInstructionPackage
}

export interface OpenHandsRecordResultRequest {
  summary: string
  output: string
  conclusion: ToolRunConclusion
}

// ---------------------------------------------------------------------------
// PR draft workflow (Task 28)
// ---------------------------------------------------------------------------

export type PullRequestDraftStatus =
  | 'draft_prepared'
  | 'awaiting_approval'
  | 'approved_for_creation'
  | 'created'
  | 'failed'
  | 'closed'
  | 'cancelled'

export type PullRequestDraftProvider = 'manual' | 'local' | 'github'

export interface PullRequestDraftCreate {
  code_repository_id: string
  dev_task_id?: string | null
  subtask_id?: string | null
  tool_run_id?: string | null
  title?: string | null
  body?: string | null
  source_branch?: string | null
  target_branch?: string
  provider?: PullRequestDraftProvider
}

export interface PullRequestDraftUpdate {
  title?: string
  body?: string
  source_branch?: string
  target_branch?: string
  status?: PullRequestDraftStatus
  external_pr_url?: string | null
  external_pr_number?: number | null
  error_message?: string | null
}

export interface PullRequestDraft {
  id: string
  project_id: string
  code_repository_id: string
  dev_task_id: string | null
  subtask_id: string | null
  tool_run_id: string | null
  title: string
  body: string
  source_branch: string
  target_branch: string
  status: PullRequestDraftStatus
  provider: PullRequestDraftProvider
  external_pr_url: string | null
  external_pr_number: number | null
  created_by: string
  error_message: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
}

// ---------------------------------------------------------------------------
// PR review integration foundation (Task 29)
// ---------------------------------------------------------------------------

export type PullRequestReviewProvider = 'kody' | 'manual' | 'custom'

export type PullRequestReviewStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type PullRequestReviewConclusion =
  | 'approved'
  | 'changes_requested'
  | 'comment_only'
  | 'failed'
  | 'skipped'
  | 'requires_human_review'

export type PullRequestReviewFindingSeverity = 'blocking' | 'warning' | 'info'

export type PullRequestReviewFindingCategory =
  | 'security'
  | 'tests'
  | 'correctness'
  | 'maintainability'
  | 'performance'
  | 'scope'
  | 'style'

export interface PullRequestReviewFinding {
  severity?: PullRequestReviewFindingSeverity | null
  category?: PullRequestReviewFindingCategory | null
  message: string
  file_path?: string | null
  line?: number | null
  recommendation?: string | null
}

export interface PullRequestReviewCreate {
  provider?: PullRequestReviewProvider
  mode?: 'manual' | 'prepare'
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
  conclusion?: PullRequestReviewConclusion | null
  external_review_url?: string | null
}

export interface PullRequestReviewUpdate {
  status?: PullRequestReviewStatus
  conclusion?: PullRequestReviewConclusion | null
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
  external_review_url?: string | null
  error_message?: string | null
}

export interface PullRequestReviewComplete {
  conclusion: PullRequestReviewConclusion
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
}

export interface PullRequestReview {
  id: string
  project_id: string
  code_repository_id: string
  pr_draft_id: string
  provider: PullRequestReviewProvider
  status: PullRequestReviewStatus
  conclusion: PullRequestReviewConclusion | null
  summary: string
  findings: PullRequestReviewFinding[]
  recommendations: string | null
  raw_output: string | null
  artifact_id: string | null
  external_review_url: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  error_message: string | null
}

// CI failure ingestion and analysis (Task 30)

export type CIEventProvider =
  | "github_actions"
  | "gitlab_ci"
  | "circleci"
  | "manual"
  | "custom"

export type CIEventStatus = "queued" | "in_progress" | "completed" | "failed"

export type CIEventConclusion =
  | "success"
  | "failure"
  | "cancelled"
  | "skipped"
  | "timed_out"
  | "neutral"
  | "unknown"

export interface CIEventCreate {
  code_repository_id?: string | null
  pr_draft_id?: string | null
  dev_task_id?: string | null
  subtask_id?: string | null
  check_run_id?: string | null
  provider: CIEventProvider
  external_run_id?: string | null
  workflow_name?: string | null
  job_name?: string | null
  branch?: string | null
  commit_sha?: string | null
  pr_number?: number | null
  pr_url?: string | null
  status: CIEventStatus
  conclusion: CIEventConclusion
  failure_summary?: string | null
  logs_excerpt?: string | null
  raw_payload?: Record<string, unknown> | null
}

export interface CIEvent {
  id: string
  project_id: string
  code_repository_id: string | null
  pr_draft_id: string | null
  dev_task_id: string | null
  subtask_id: string | null
  check_run_id: string | null
  provider: CIEventProvider
  external_run_id: string | null
  workflow_name: string | null
  job_name: string | null
  branch: string | null
  commit_sha: string | null
  pr_number: number | null
  pr_url: string | null
  status: CIEventStatus
  conclusion: CIEventConclusion
  failure_summary: string | null
  logs_excerpt: string | null
  raw_payload: Record<string, unknown> | null
  artifact_id: string | null
  created_at: string
  updated_at: string
}

export type CIAnalysisStatus = "pending" | "running" | "completed" | "failed"

export type CIAnalysisConclusion =
  | "flaky_test"
  | "code_regression"
  | "dependency_issue"
  | "configuration_issue"
  | "infrastructure_issue"
  | "unknown"
  | "needs_human_review"

export interface CIAnalysisCreate {
  provider?: string | null
}

export interface CIAnalysis {
  id: string
  project_id: string
  ci_event_id: string
  provider: string
  model: string
  status: CIAnalysisStatus
  conclusion: CIAnalysisConclusion | null
  summary: string
  likely_root_causes: string[]
  suggested_fixes: string[]
  affected_areas: string[]
  recommended_next_action: string | null
  raw_output: string | null
  artifact_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Production / incident workflow (Task 31)
// ---------------------------------------------------------------------------

export type IncidentSeverity = "sev1" | "sev2" | "sev3" | "sev4" | "unknown"

export type IncidentStatus =
  | "reported"
  | "triaging"
  | "remediation_planned"
  | "remediation_approved"
  | "resolved"
  | "closed"
  | "cancelled"

export type IncidentSource =
  | "manual"
  | "ci_failure"
  | "production_log"
  | "monitoring"
  | "user_report"
  | "support"
  | "custom"

export interface IncidentCreate {
  code_repository_id?: string | null
  ci_event_id?: string | null
  pr_draft_id?: string | null
  dev_task_id?: string | null
  subtask_id?: string | null
  title: string
  description: string
  severity?: IncidentSeverity
  source?: IncidentSource
  environment?: string | null
  affected_area?: string | null
  started_at?: string | null
  detected_at?: string | null
  external_url?: string | null
  evidence?: string | null
}

export interface IncidentUpdate {
  title?: string | null
  description?: string | null
  severity?: IncidentSeverity | null
  status?: IncidentStatus | null
  source?: IncidentSource | null
  environment?: string | null
  affected_area?: string | null
  evidence?: string | null
  external_url?: string | null
  resolved_at?: string | null
}

export interface Incident {
  id: string
  project_id: string
  code_repository_id: string | null
  ci_event_id: string | null
  pr_draft_id: string | null
  dev_task_id: string | null
  subtask_id: string | null
  title: string
  description: string
  severity: IncidentSeverity
  status: IncidentStatus
  source: IncidentSource
  environment: string | null
  affected_area: string | null
  started_at: string | null
  detected_at: string | null
  resolved_at: string | null
  external_url: string | null
  evidence: string | null
  created_at: string
  updated_at: string
}

export type IncidentAnalysisStatus = "pending" | "running" | "completed" | "failed"

export type IncidentAnalysisConclusion =
  | "code_regression"
  | "configuration_issue"
  | "infrastructure_issue"
  | "dependency_issue"
  | "data_issue"
  | "security_issue"
  | "flaky_external_service"
  | "unknown"
  | "needs_human_review"

export interface IncidentAnalysisCreate {
  provider?: string | null
}

export interface IncidentAnalysis {
  id: string
  project_id: string
  incident_id: string
  provider: string
  model: string
  status: IncidentAnalysisStatus
  conclusion: IncidentAnalysisConclusion | null
  summary: string
  impact_assessment: string | null
  likely_root_causes: string[]
  immediate_actions: string[]
  remediation_plan: string[]
  prevention_actions: string[]
  affected_areas: string[]
  recommended_next_action: string | null
  raw_output: string | null
  artifact_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface RemediationWorkItemDraft {
  incident_id: string
  project_id: string
  analysis_id: string | null
  title: string
  description: string
  suggested_acceptance_criteria: string[]
  requires_human_approval: boolean
  created_at: string
}

// ---------------------------------------------------------------------------
// Project memory learning loop (Task 32)
// ---------------------------------------------------------------------------

export type MemoryCandidateSourceType =
  | "manual"
  | "approval"
  | "audit_event"
  | "check_run"
  | "tool_run"
  | "pr_review"
  | "ci_analysis"
  | "incident_analysis"
  | "dev_task"
  | "subtask"
  | "requirement"
  | "artifact"

export type MemoryCandidateMemoryType =
  | "architecture_decision"
  | "project_rule"
  | "coding_standard"
  | "testing_rule"
  | "deployment_rule"
  | "approved_approach"
  | "rejected_approach"
  | "known_risk"
  | "known_failure_pattern"
  | "human_feedback"
  | "important_file"
  | "prompt_note"
  | "qa_learning"
  | "incident_learning"
  | "cost_note"
  | "custom"

export type MemoryCandidateStatus = "proposed" | "approved" | "rejected" | "superseded"
export type MemoryLearningRunStatus = "pending" | "running" | "completed" | "failed"

export interface ProjectMemoryCandidateCreate {
  source_type?: MemoryCandidateSourceType
  source_id?: string | null
  memory_type: MemoryCandidateMemoryType
  title: string
  content: string
  tags?: string[]
  confidence?: number | null
  proposed_by?: string | null
  provider?: string | null
  model?: string | null
  learning_run_id?: string | null
}

export interface ProjectMemoryCandidateUpdate {
  memory_type?: MemoryCandidateMemoryType
  title?: string
  content?: string
  tags?: string[]
  confidence?: number | null
}

export interface MemoryCandidateRejectRequest {
  reason?: string | null
}

export interface ProjectMemoryCandidate {
  id: string
  project_id: string
  learning_run_id: string | null
  source_type: MemoryCandidateSourceType
  source_id: string | null
  memory_type: MemoryCandidateMemoryType
  title: string
  content: string
  tags: string[]
  confidence: number | null
  status: MemoryCandidateStatus
  proposed_by: string | null
  provider: string | null
  model: string | null
  artifact_id: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  rejected_at: string | null
}

export interface MemoryLearningRunCreate {
  source_type: MemoryCandidateSourceType
  source_id: string
  provider?: string | null
}

export interface MemoryLearningRun {
  id: string
  project_id: string
  source_type: MemoryCandidateSourceType
  source_id: string
  provider: string
  model: string
  status: MemoryLearningRunStatus
  summary: string
  candidates_created: number
  candidate_ids: string[]
  artifact_id: string | null
  raw_output: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
