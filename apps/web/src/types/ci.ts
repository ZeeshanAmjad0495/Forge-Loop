export type CIEventProvider =
  | "github_actions"
  | "gitlab_ci"
  | "circleci"
  | "manual"
  | "custom"

export type CIEventStatus = "queued" | "in_progress" | "completed" | "failed"

export type CIEventConclusion =
  | "success"
  | "failure"
  | "cancelled"
  | "skipped"
  | "timed_out"
  | "neutral"
  | "unknown"

export interface CIEventCreate {
  code_repository_id?: string | null
  pr_draft_id?: string | null
  dev_task_id?: string | null
  subtask_id?: string | null
  check_run_id?: string | null
  provider: CIEventProvider
  external_run_id?: string | null
  workflow_name?: string | null
  job_name?: string | null
  branch?: string | null
  commit_sha?: string | null
  pr_number?: number | null
  pr_url?: string | null
  status: CIEventStatus
  conclusion: CIEventConclusion
  failure_summary?: string | null
  logs_excerpt?: string | null
  raw_payload?: Record<string, unknown> | null
}

export interface CIEvent {
  id: string
  project_id: string
  code_repository_id: string | null
  pr_draft_id: string | null
  dev_task_id: string | null
  subtask_id: string | null
  check_run_id: string | null
  provider: CIEventProvider
  external_run_id: string | null
  workflow_name: string | null
  job_name: string | null
  branch: string | null
  commit_sha: string | null
  pr_number: number | null
  pr_url: string | null
  status: CIEventStatus
  conclusion: CIEventConclusion
  failure_summary: string | null
  logs_excerpt: string | null
  raw_payload: Record<string, unknown> | null
  artifact_id: string | null
  created_at: string
  updated_at: string
}

export type CIAnalysisStatus = "pending" | "running" | "completed" | "failed"

export type CIAnalysisConclusion =
  | "flaky_test"
  | "code_regression"
  | "dependency_issue"
  | "configuration_issue"
  | "infrastructure_issue"
  | "unknown"
  | "needs_human_review"

export interface CIAnalysisCreate {
  provider?: string | null
}

export interface CIAnalysis {
  id: string
  project_id: string
  ci_event_id: string
  provider: string
  model: string
  status: CIAnalysisStatus
  conclusion: CIAnalysisConclusion | null
  summary: string
  likely_root_causes: string[]
  suggested_fixes: string[]
  affected_areas: string[]
  recommended_next_action: string | null
  raw_output: string | null
  artifact_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
