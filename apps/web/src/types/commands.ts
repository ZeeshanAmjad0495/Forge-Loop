export type CommandType =
  | 'test'
  | 'build'
  | 'lint'
  | 'typecheck'
  | 'coverage'
  | 'security_scan'
  | 'utility'
  | 'custom'

export type CommandRunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'timed_out'
  | 'blocked'
  | 'cancelled'

export type CommandRunConclusion =
  | 'success'
  | 'failure'
  | 'neutral'
  | 'skipped'
  | 'blocked'
  | 'timed_out'

export type CommandRunTargetType =
  | 'project'
  | 'requirement'
  | 'epic'
  | 'dev_task'
  | 'subtask'
  | 'check_definition'
  | 'check_run'
  | 'tool_run'
  | 'manual'

export interface CommandDefinitionCreate {
  workspace_id?: string | null
  code_repository_id?: string | null
  name: string
  command: string
  args?: string[]
  command_type?: CommandType
  enabled?: boolean
  requires_approval?: boolean
  timeout_seconds?: number
  working_directory?: string | null
  description?: string | null
}

export interface CommandDefinitionUpdate {
  name?: string | null
  command?: string | null
  args?: string[] | null
  command_type?: CommandType | null
  enabled?: boolean | null
  requires_approval?: boolean | null
  timeout_seconds?: number | null
  working_directory?: string | null
  description?: string | null
}

export interface CommandDefinition {
  id: string
  project_id: string
  workspace_id: string | null
  code_repository_id: string | null
  name: string
  command: string
  args: string[]
  command_type: CommandType
  enabled: boolean
  requires_approval: boolean
  timeout_seconds: number
  working_directory: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface CommandRunCreate {
  command_definition_id?: string | null
  command?: string | null
  args?: string[] | null
  target_type?: CommandRunTargetType
  target_id?: string | null
  timeout_seconds?: number | null
  working_directory?: string | null
}

export interface CommandRun {
  id: string
  project_id: string
  workspace_id: string
  command_definition_id: string | null
  target_type: CommandRunTargetType
  target_id: string | null
  command: string
  args: string[]
  status: CommandRunStatus
  conclusion: CommandRunConclusion | null
  exit_code: number | null
  stdout: string | null
  stderr: string | null
  output_summary: string | null
  artifact_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  error_message: string | null
}
