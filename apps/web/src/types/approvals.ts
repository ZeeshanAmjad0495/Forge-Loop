export type ApprovalTargetType =
  | 'requirement_analysis' | 'task_decomposition' | 'dev_task' | 'subtask' | 'artifact'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'needs_revision'

export interface ApprovalCreate {
  project_id: string
  target_type: ApprovalTargetType
  target_id: string
  feedback?: string | null
}

export interface ApprovalDecision {
  status: 'approved' | 'rejected' | 'needs_revision'
  feedback?: string | null
}

export interface Approval {
  id: string
  project_id: string
  target_type: ApprovalTargetType
  target_id: string
  status: ApprovalStatus
  requested_by: string
  decided_by: string | null
  feedback: string | null
  created_at: string
  updated_at: string
  decided_at: string | null
}
