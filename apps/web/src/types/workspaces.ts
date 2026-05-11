export type WorkspaceType =
  | 'local_existing'
  | 'local_created'
  | 'git_clone_pending'
  | 'manual'

export type WorkspaceStatus =
  | 'registered'
  | 'ready'
  | 'missing'
  | 'invalid'
  | 'archived'

export interface WorkspaceCreate {
  code_repository_id?: string | null
  name: string
  root_path?: string | null
  workspace_type?: WorkspaceType
  description?: string | null
  create_directory?: boolean
}

export interface WorkspaceUpdate {
  name?: string | null
  description?: string | null
  status?: WorkspaceStatus | null
  code_repository_id?: string | null
}

export interface Workspace {
  id: string
  project_id: string
  code_repository_id: string | null
  name: string
  root_path: string
  workspace_type: WorkspaceType
  status: WorkspaceStatus
  description: string | null
  created_at: string
  updated_at: string
  last_inspected_at: string | null
  error_message: string | null
}

export interface WorkspaceInspection {
  workspace_id: string
  exists: boolean
  is_directory: boolean
  is_git_repo: boolean
  current_branch: string | null
  dirty: boolean
  file_count_estimate: number
  blocked_path_hits: string[]
  notes: string[]
}
