export type ReviewFeedbackSource = 'human' | 'kody' | 'github' | 'manual' | 'custom'

export type ReviewFeedbackStatus =
  | 'open'
  | 'accepted'
  | 'revision_planned'
  | 'in_progress'
  | 'resolved'
  | 'rejected'
  | 'deferred'

export type ReviewFeedbackSeverity = 'blocking' | 'warning' | 'info'

export type ReviewFeedbackCategory =
  | 'correctness'
  | 'tests'
  | 'security'
  | 'maintainability'
  | 'performance'
  | 'scope'
  | 'style'
  | 'documentation'
  | 'other'

export interface ReviewFeedbackCreate {
  pr_review_id?: string | null
  source?: ReviewFeedbackSource
  author?: string | null
  severity?: ReviewFeedbackSeverity
  category?: ReviewFeedbackCategory
  summary: string
  details?: string | null
  file_path?: string | null
  line?: number | null
  recommendation?: string | null
}

export interface ReviewFeedbackUpdate {
  status?: ReviewFeedbackStatus
  severity?: ReviewFeedbackSeverity
  category?: ReviewFeedbackCategory
  summary?: string
  details?: string | null
  recommendation?: string | null
}

export interface ReviewFeedbackResolve {
  resolution_summary: string
}

export interface ReviewFeedback {
  id: string
  project_id: string
  pr_draft_id: string
  pr_review_id: string | null
  source: ReviewFeedbackSource
  author: string | null
  status: ReviewFeedbackStatus
  severity: ReviewFeedbackSeverity
  category: ReviewFeedbackCategory
  summary: string
  details: string | null
  file_path: string | null
  line: number | null
  recommendation: string | null
  revision_work_item_id: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  resolution_summary: string | null
}

export interface ReviewFeedbackImportResponse {
  pr_review_id: string
  pr_draft_id: string
  created: number
  skipped: number
  feedback_items: ReviewFeedback[]
}

export type RevisionWorkItemStatus =
  | 'proposed'
  | 'approved'
  | 'in_progress'
  | 'implemented'
  | 'checks_passed'
  | 'ready_for_review'
  | 'resolved'
  | 'rejected'

export interface RevisionWorkItemCreate {
  workspace_id: string
  workspace_branch_id?: string | null
  dev_task_id?: string | null
  subtask_id?: string | null
  title?: string | null
  description?: string | null
  approval_required?: boolean
}

export interface RevisionWorkItemUpdate {
  status?: RevisionWorkItemStatus
  title?: string
  description?: string
  workspace_branch_id?: string | null
}

export interface RevisionWorkItem {
  id: string
  project_id: string
  pr_draft_id: string
  review_feedback_id: string
  dev_task_id: string | null
  subtask_id: string | null
  workspace_id: string
  workspace_branch_id: string | null
  title: string
  description: string
  status: RevisionWorkItemStatus
  requires_approval: boolean
  created_at: string
  updated_at: string
  approved_at: string | null
  resolved_at: string | null
}

export interface RevisionPlanResponse {
  review_feedback: ReviewFeedback
  revision_work_item: RevisionWorkItem
}
