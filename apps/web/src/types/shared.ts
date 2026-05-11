export type AssigneeType = 'human' | 'agent' | 'unassigned'
export type DevTaskStatus = 'proposed' | 'ready' | 'in_progress' | 'blocked' | 'completed'

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

export interface ProviderInfo {
  name: string
  configured: boolean
  default_model: string
}

export interface ProvidersResponse {
  default_provider: string
  providers: ProviderInfo[]
}
