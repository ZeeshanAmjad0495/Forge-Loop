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
  agent_type: 'planning' | 'requirement_analysis' | 'task_decomposition'
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
  artifact_type: 'implementation_brief' | 'requirement_analysis' | 'task_decomposition'
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
}

export interface SubtaskUpdate {
  title?: string
  description?: string
  status?: DevTaskStatus
  sequence_order?: number
  acceptance_criteria?: string[]
  qa_required?: boolean
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
  created_at: string
  updated_at: string
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
