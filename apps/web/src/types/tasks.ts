import type { AgentRun, Artifact, AssigneeType, DevTaskStatus } from './shared'

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

export interface TaskDecompositionResponse {
  agent_run: AgentRun
  artifact: Artifact
  dev_tasks: DevTask[]
  subtasks: Subtask[]
}

export interface PlanningRunResponse {
  agent_run: AgentRun
  artifact: Artifact
}
