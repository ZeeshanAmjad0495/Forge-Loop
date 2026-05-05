export interface Ticket {
  id: string
  title: string
  description: string
  status: 'created' | 'brief_generated'
  created_at: string
  updated_at: string
}

export interface AgentRun {
  id: string
  ticket_id: string
  agent_type: 'planning'
  provider: string
  model: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error_message: string | null
}

export interface Artifact {
  id: string
  ticket_id: string
  agent_run_id: string
  artifact_type: 'implementation_brief'
  content: string
  created_at: string
}

export interface PlanningRunResponse {
  agent_run: AgentRun
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
