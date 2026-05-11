export type CodeRepositoryProvider = 'github' | 'gitlab' | 'bitbucket' | 'other'
export type CodeRepositoryStatus = 'active' | 'disabled'

export interface CodeRepositoryCreate {
  provider?: CodeRepositoryProvider
  repo_url: string
  name: string
  default_branch?: string
}

export interface CodeRepositoryUpdate {
  provider?: CodeRepositoryProvider | null
  repo_url?: string | null
  name?: string | null
  default_branch?: string | null
  status?: CodeRepositoryStatus | null
}

export interface CodeRepository {
  id: string
  project_id: string
  provider: CodeRepositoryProvider
  repo_url: string
  name: string
  default_branch: string
  status: CodeRepositoryStatus
  created_at: string
  updated_at: string
}

export interface RepoSafetyProfileUpsert {
  work_safe_mode?: boolean
  allowed_actions?: string[]
  blocked_paths?: string[]
  required_checks?: string[]
  requires_approval_for?: string[]
  protected_branches?: string[]
  notes?: string
}

export interface RepoSafetyProfile {
  id: string
  project_id: string
  code_repository_id: string
  work_safe_mode: boolean
  allowed_actions: string[]
  blocked_paths: string[]
  required_checks: string[]
  requires_approval_for: string[]
  protected_branches: string[]
  notes: string
  created_at: string
  updated_at: string
}
