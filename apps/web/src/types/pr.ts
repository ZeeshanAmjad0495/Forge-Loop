export type PullRequestDraftStatus =
  | 'draft_prepared'
  | 'awaiting_approval'
  | 'approved_for_creation'
  | 'created'
  | 'failed'
  | 'closed'
  | 'cancelled'

export type PullRequestDraftProvider = 'manual' | 'local' | 'github'

export interface PullRequestDraftCreate {
  code_repository_id: string
  dev_task_id?: string | null
  subtask_id?: string | null
  tool_run_id?: string | null
  title?: string | null
  body?: string | null
  source_branch?: string | null
  target_branch?: string
  provider?: PullRequestDraftProvider
}

export interface PullRequestDraftUpdate {
  title?: string
  body?: string
  source_branch?: string
  target_branch?: string
  status?: PullRequestDraftStatus
  external_pr_url?: string | null
  external_pr_number?: number | null
  error_message?: string | null
}

export interface PullRequestDraft {
  id: string
  project_id: string
  code_repository_id: string
  dev_task_id: string | null
  subtask_id: string | null
  tool_run_id: string | null
  title: string
  body: string
  source_branch: string
  target_branch: string
  status: PullRequestDraftStatus
  provider: PullRequestDraftProvider
  external_pr_url: string | null
  external_pr_number: number | null
  created_by: string
  error_message: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
}

export type PullRequestReviewProvider = 'kody' | 'manual' | 'custom'

export type PullRequestReviewStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type PullRequestReviewConclusion =
  | 'approved'
  | 'changes_requested'
  | 'comment_only'
  | 'failed'
  | 'skipped'
  | 'requires_human_review'

export type PullRequestReviewFindingSeverity = 'blocking' | 'warning' | 'info'

export type PullRequestReviewFindingCategory =
  | 'security'
  | 'tests'
  | 'correctness'
  | 'maintainability'
  | 'performance'
  | 'scope'
  | 'style'

export interface PullRequestReviewFinding {
  severity?: PullRequestReviewFindingSeverity | null
  category?: PullRequestReviewFindingCategory | null
  message: string
  file_path?: string | null
  line?: number | null
  recommendation?: string | null
}

export interface PullRequestReviewCreate {
  provider?: PullRequestReviewProvider
  mode?: 'manual' | 'prepare'
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
  conclusion?: PullRequestReviewConclusion | null
  external_review_url?: string | null
}

export interface PullRequestReviewUpdate {
  status?: PullRequestReviewStatus
  conclusion?: PullRequestReviewConclusion | null
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
  external_review_url?: string | null
  error_message?: string | null
}

export interface PullRequestReviewComplete {
  conclusion: PullRequestReviewConclusion
  summary?: string | null
  findings?: PullRequestReviewFinding[]
  recommendations?: string | null
  raw_output?: string | null
}

export interface PullRequestReview {
  id: string
  project_id: string
  code_repository_id: string
  pr_draft_id: string
  provider: PullRequestReviewProvider
  status: PullRequestReviewStatus
  conclusion: PullRequestReviewConclusion | null
  summary: string
  findings: PullRequestReviewFinding[]
  recommendations: string | null
  raw_output: string | null
  artifact_id: string | null
  external_review_url: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  error_message: string | null
}
