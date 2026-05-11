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
  execution_enabled: boolean
}

export interface OpenHandsRecordResultRequest {
  summary: string
  output: string
  conclusion: ToolRunConclusion
}

export type OpenHandsExecuteMode = 'dry_run' | 'local'

export type OpenHandsChangeType = 'added' | 'modified' | 'deleted'

export interface OpenHandsChangedPath {
  path: string
  change_type: OpenHandsChangeType
}

export interface OpenHandsExecuteRequest {
  workspace_id: string
  tool_runner_definition_id?: string | null
  approval_id?: string | null
  mode: OpenHandsExecuteMode
  timeout_seconds?: number | null
}

export interface OpenHandsExecutionSummary {
  mode: OpenHandsExecuteMode
  exit_code: number | null
  timed_out: boolean
  duration_seconds: number
  changed_paths: OpenHandsChangedPath[]
  blocked_path_changes: string[]
  stdout_tail: string
  stderr_tail: string
  snapshot_truncated: boolean
  workspace_id: string | null
}

export interface OpenHandsExecuteResponse {
  tool_run: ToolRun
  instruction_package: OpenHandsInstructionPackage
  execution_summary: OpenHandsExecutionSummary
}
