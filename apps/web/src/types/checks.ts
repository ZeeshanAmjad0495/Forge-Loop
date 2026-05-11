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
  command_run_id: string | null
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface CheckExecutionRequest {
  workspace_id: string
  target_type?: CheckRunTargetType
  target_id?: string | null
  timeout_seconds?: number | null
}

export interface CheckExecutionResponse {
  check_run: CheckRun
  command_run: import('./commands').CommandRun
}
