from datetime import datetime
from typing import Literal

from pydantic import BaseModel

WorkSafePolicyStatus = Literal["draft", "active", "archived"]
WorkSafePolicyLevel = Literal["personal", "strict", "enterprise_candidate"]
WorkSafeActionType = Literal[
    "external_llm_call",
    "github_push",
    "openhands_execution",
    "command_execution",
    "artifact_export",
    "audit_export",
    "cloud_storage",
    "secret_access",
]


class WorkSafePolicyCreate(BaseModel):
    name: str
    project_id: str | None = None
    status: WorkSafePolicyStatus = "draft"
    policy_level: WorkSafePolicyLevel = "personal"
    require_approval_for: list[WorkSafeActionType] = []
    restricted_providers: list[str] = []
    restricted_integrations: list[str] = []
    blocked_path_patterns: list[str] = []
    sensitive_field_patterns: list[str] = []
    allow_external_llms: bool = True
    allow_cloud_storage: bool = True
    allow_github_push: bool = True
    allow_openhands_execution: bool = True
    audit_export_enabled: bool = True
    notes: str | None = None


class WorkSafePolicyUpdate(BaseModel):
    name: str | None = None
    status: WorkSafePolicyStatus | None = None
    policy_level: WorkSafePolicyLevel | None = None
    require_approval_for: list[WorkSafeActionType] | None = None
    restricted_providers: list[str] | None = None
    restricted_integrations: list[str] | None = None
    blocked_path_patterns: list[str] | None = None
    sensitive_field_patterns: list[str] | None = None
    allow_external_llms: bool | None = None
    allow_cloud_storage: bool | None = None
    allow_github_push: bool | None = None
    allow_openhands_execution: bool | None = None
    audit_export_enabled: bool | None = None
    notes: str | None = None


class WorkSafePolicy(BaseModel):
    id: str
    project_id: str | None = None
    name: str
    status: WorkSafePolicyStatus = "draft"
    policy_level: WorkSafePolicyLevel = "personal"
    require_approval_for: list[WorkSafeActionType] = []
    restricted_providers: list[str] = []
    restricted_integrations: list[str] = []
    blocked_path_patterns: list[str] = []
    sensitive_field_patterns: list[str] = []
    allow_external_llms: bool = True
    allow_cloud_storage: bool = True
    allow_github_push: bool = True
    allow_openhands_execution: bool = True
    audit_export_enabled: bool = True
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class WorkSafeCheckRequest(BaseModel):
    action: WorkSafeActionType
    provider: str | None = None
    integration: str | None = None
    target_path: str | None = None


class WorkSafeCheckResponse(BaseModel):
    action: WorkSafeActionType
    decision: Literal["allow", "require_approval", "deny"]
    policy_id: str | None = None
    policy_level: WorkSafePolicyLevel | None = None
    reasons: list[str] = []


# -- Audit export request -------------------------------------------------

AuditExportStatus = Literal[
    "requested",
    "running",
    "completed",
    "failed",
    "cancelled",
]
AuditExportFormat = Literal["json", "ndjson", "csv"]


class AuditExportRequestCreate(BaseModel):
    project_id: str | None = None
    format: AuditExportFormat = "json"
    scope: str = "all"
    requested_by: str | None = None


class AuditExportRequestUpdate(BaseModel):
    status: AuditExportStatus | None = None
    artifact_id: str | None = None
    error_message: str | None = None


class AuditExportRequest(BaseModel):
    id: str
    project_id: str | None = None
    requested_by: str | None = None
    status: AuditExportStatus = "requested"
    format: AuditExportFormat = "json"
    scope: str = "all"
    artifact_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
