from datetime import datetime
from typing import Literal

from pydantic import BaseModel

IncidentSeverity = Literal["sev1", "sev2", "sev3", "sev4", "unknown"]
IncidentStatus = Literal[
    "reported",
    "triaging",
    "remediation_planned",
    "remediation_approved",
    "resolved",
    "closed",
    "cancelled",
]
IncidentSource = Literal[
    "manual",
    "ci_failure",
    "production_log",
    "monitoring",
    "user_report",
    "support",
    "custom",
]


class IncidentCreate(BaseModel):
    code_repository_id: str | None = None
    ci_event_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    title: str
    description: str
    severity: IncidentSeverity = "unknown"
    source: IncidentSource = "manual"
    environment: str | None = None
    affected_area: str | None = None
    started_at: datetime | None = None
    detected_at: datetime | None = None
    external_url: str | None = None
    evidence: str | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    source: IncidentSource | None = None
    environment: str | None = None
    affected_area: str | None = None
    evidence: str | None = None
    external_url: str | None = None
    resolved_at: datetime | None = None


class Incident(BaseModel):
    id: str
    project_id: str
    code_repository_id: str | None = None
    ci_event_id: str | None = None
    pr_draft_id: str | None = None
    dev_task_id: str | None = None
    subtask_id: str | None = None
    title: str
    description: str
    severity: IncidentSeverity = "unknown"
    status: IncidentStatus = "reported"
    source: IncidentSource = "manual"
    environment: str | None = None
    affected_area: str | None = None
    started_at: datetime | None = None
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    external_url: str | None = None
    evidence: str | None = None
    created_at: datetime
    updated_at: datetime


IncidentAnalysisStatus = Literal["pending", "running", "completed", "failed"]
IncidentAnalysisConclusion = Literal[
    "code_regression",
    "configuration_issue",
    "infrastructure_issue",
    "dependency_issue",
    "data_issue",
    "security_issue",
    "flaky_external_service",
    "unknown",
    "needs_human_review",
]


class IncidentAnalysisCreate(BaseModel):
    provider: str | None = None
    expensive_approved: bool = False


class IncidentAnalysis(BaseModel):
    id: str
    project_id: str
    incident_id: str
    provider: str
    model: str
    status: IncidentAnalysisStatus
    conclusion: IncidentAnalysisConclusion | None = None
    summary: str = ""
    impact_assessment: str | None = None
    likely_root_causes: list[str] = []
    immediate_actions: list[str] = []
    remediation_plan: list[str] = []
    prevention_actions: list[str] = []
    affected_areas: list[str] = []
    recommended_next_action: str | None = None
    raw_output: str | None = None
    artifact_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class RemediationWorkItemDraft(BaseModel):
    """Non-persisted draft of a remediation DevTask suggestion.

    Returned by ``POST /incidents/{id}/prepare-remediation`` so a human can
    create a DevTask manually after review. ForgeLoop never auto-creates a
    coding-runner work item from an incident.
    """

    incident_id: str
    project_id: str
    analysis_id: str | None = None
    title: str
    description: str
    suggested_acceptance_criteria: list[str] = []
    requires_human_approval: bool = True
    created_at: datetime
