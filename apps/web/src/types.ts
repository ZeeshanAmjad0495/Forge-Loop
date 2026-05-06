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
  agent_type: 'planning' | 'requirement_analysis'
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
  artifact_type: 'implementation_brief' | 'requirement_analysis'
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
