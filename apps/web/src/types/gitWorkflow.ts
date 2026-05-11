export type WorkspaceBranchStatus =
  | 'prepared'
  | 'active'
  | 'clean'
  | 'dirty'
  | 'committed'
  | 'failed'
  | 'archived'

export interface WorkspaceBranchCreate {
  dev_task_id?: string | null
  subtask_id?: string | null
  tool_run_id?: string | null
  base_branch?: string | null
  name?: string | null
  approval_id?: string | null
}

export interface WorkspaceBranch {
  id: string
  project_id: string
  workspace_id: string
  code_repository_id: string | null
  dev_task_id: string | null
  subtask_id: string | null
  tool_run_id: string | null
  name: string
  base_branch: string | null
  current_branch: string | null
  status: WorkspaceBranchStatus
  created_at: string
  updated_at: string
  last_inspected_at: string | null
  error_message: string | null
}

export interface GitInspectionResponse {
  workspace_id: string
  is_git_repo: boolean
  current_branch: string | null
  base_branch: string | null
  dirty: boolean
  changed_files: string[]
  untracked_files: string[]
  diff_stat: string
  ahead_behind: null
  notes: string[]
  git_workflow_enabled: boolean
  git_commit_enabled: boolean
}

export interface WorkspaceBranchResponse {
  workspace_branch: WorkspaceBranch
  inspection: GitInspectionResponse
}

export type GitCommitStatus = 'prepared' | 'committed' | 'failed'

export interface GitCommitCreate {
  message: string
  approval_id?: string | null
  include_paths?: string[] | null
}

export interface GitCommitRecord {
  id: string
  project_id: string
  workspace_id: string
  workspace_branch_id: string
  commit_sha: string | null
  message: string
  status: GitCommitStatus
  changed_files: string[]
  diff_stat: string
  artifact_id: string | null
  created_at: string
  updated_at: string
  error_message: string | null
}
