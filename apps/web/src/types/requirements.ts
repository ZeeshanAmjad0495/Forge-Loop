import type { AgentRun, Artifact } from './shared'

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

export interface RequirementGenerationResponse {
  agent_run: AgentRun
  artifact: Artifact
  requirements: Requirement[]
}
