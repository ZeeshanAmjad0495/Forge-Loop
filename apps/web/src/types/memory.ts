export type MemoryCandidateSourceType =
  | "manual"
  | "approval"
  | "audit_event"
  | "check_run"
  | "tool_run"
  | "pr_review"
  | "ci_analysis"
  | "incident_analysis"
  | "dev_task"
  | "subtask"
  | "requirement"
  | "artifact"

export type MemoryCandidateMemoryType =
  | "architecture_decision"
  | "project_rule"
  | "coding_standard"
  | "testing_rule"
  | "deployment_rule"
  | "approved_approach"
  | "rejected_approach"
  | "known_risk"
  | "known_failure_pattern"
  | "human_feedback"
  | "important_file"
  | "prompt_note"
  | "qa_learning"
  | "incident_learning"
  | "cost_note"
  | "custom"

export type MemoryCandidateStatus = "proposed" | "approved" | "rejected" | "superseded"
export type MemoryLearningRunStatus = "pending" | "running" | "completed" | "failed"

export interface ProjectMemoryCandidateCreate {
  source_type?: MemoryCandidateSourceType
  source_id?: string | null
  memory_type: MemoryCandidateMemoryType
  title: string
  content: string
  tags?: string[]
  confidence?: number | null
  proposed_by?: string | null
  provider?: string | null
  model?: string | null
  learning_run_id?: string | null
}

export interface ProjectMemoryCandidateUpdate {
  memory_type?: MemoryCandidateMemoryType
  title?: string
  content?: string
  tags?: string[]
  confidence?: number | null
}

export interface MemoryCandidateRejectRequest {
  reason?: string | null
}

export interface ProjectMemoryCandidate {
  id: string
  project_id: string
  learning_run_id: string | null
  source_type: MemoryCandidateSourceType
  source_id: string | null
  memory_type: MemoryCandidateMemoryType
  title: string
  content: string
  tags: string[]
  confidence: number | null
  status: MemoryCandidateStatus
  proposed_by: string | null
  provider: string | null
  model: string | null
  artifact_id: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  rejected_at: string | null
}

export interface MemoryLearningRunCreate {
  source_type: MemoryCandidateSourceType
  source_id: string
  provider?: string | null
}

export interface MemoryLearningRun {
  id: string
  project_id: string
  source_type: MemoryCandidateSourceType
  source_id: string
  provider: string
  model: string
  status: MemoryLearningRunStatus
  summary: string
  candidates_created: number
  candidate_ids: string[]
  artifact_id: string | null
  raw_output: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
