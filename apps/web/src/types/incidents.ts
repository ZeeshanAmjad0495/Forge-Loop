export type IncidentSeverity = "sev1" | "sev2" | "sev3" | "sev4" | "unknown"

export type IncidentStatus =
  | "reported"
  | "triaging"
  | "remediation_planned"
  | "remediation_approved"
  | "resolved"
  | "closed"
  | "cancelled"

export type IncidentSource =
  | "manual"
  | "ci_failure"
  | "production_log"
  | "monitoring"
  | "user_report"
  | "support"
  | "custom"

export interface IncidentCreate {
  code_repository_id?: string | null
  ci_event_id?: string | null
  pr_draft_id?: string | null
  dev_task_id?: string | null
  subtask_id?: string | null
  title: string
  description: string
  severity?: IncidentSeverity
  source?: IncidentSource
  environment?: string | null
  affected_area?: string | null
  started_at?: string | null
  detected_at?: string | null
  external_url?: string | null
  evidence?: string | null
}

export interface IncidentUpdate {
  title?: string | null
  description?: string | null
  severity?: IncidentSeverity | null
  status?: IncidentStatus | null
  source?: IncidentSource | null
  environment?: string | null
  affected_area?: string | null
  evidence?: string | null
  external_url?: string | null
  resolved_at?: string | null
}

export interface Incident {
  id: string
  project_id: string
  code_repository_id: string | null
  ci_event_id: string | null
  pr_draft_id: string | null
  dev_task_id: string | null
  subtask_id: string | null
  title: string
  description: string
  severity: IncidentSeverity
  status: IncidentStatus
  source: IncidentSource
  environment: string | null
  affected_area: string | null
  started_at: string | null
  detected_at: string | null
  resolved_at: string | null
  external_url: string | null
  evidence: string | null
  created_at: string
  updated_at: string
}

export type IncidentAnalysisStatus = "pending" | "running" | "completed" | "failed"

export type IncidentAnalysisConclusion =
  | "code_regression"
  | "configuration_issue"
  | "infrastructure_issue"
  | "dependency_issue"
  | "data_issue"
  | "security_issue"
  | "flaky_external_service"
  | "unknown"
  | "needs_human_review"

export interface IncidentAnalysisCreate {
  provider?: string | null
}

export interface IncidentAnalysis {
  id: string
  project_id: string
  incident_id: string
  provider: string
  model: string
  status: IncidentAnalysisStatus
  conclusion: IncidentAnalysisConclusion | null
  summary: string
  impact_assessment: string | null
  likely_root_causes: string[]
  immediate_actions: string[]
  remediation_plan: string[]
  prevention_actions: string[]
  affected_areas: string[]
  recommended_next_action: string | null
  raw_output: string | null
  artifact_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface RemediationWorkItemDraft {
  incident_id: string
  project_id: string
  analysis_id: string | null
  title: string
  description: string
  suggested_acceptance_criteria: string[]
  requires_human_approval: boolean
  created_at: string
}
