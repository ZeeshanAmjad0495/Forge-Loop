from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

WorkflowTemplateType = Literal[
    "feature",
    "bugfix",
    "refactor",
    "security",
    "incident_followup",
    "documentation",
    "test_hardening",
    "research",
    "custom",
]
WorkflowTemplateStatus = Literal[
    "draft",
    "active",
    "archived",
]


class WorkflowStage(BaseModel):
    name: str
    stage_type: str = "custom"
    required: bool = True
    description: str = ""


class WorkflowTemplateCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    workflow_type: WorkflowTemplateType = "custom"
    status: WorkflowTemplateStatus = "draft"
    stages: list[WorkflowStage] = []
    default_required_checks: list[str] = []
    approval_gates: list[str] = []
    review_checklist: list[str] = []
    memory_capture_rules: list[str] = []
    recommended_models: list[str] = []
    tags: list[str] = []


class WorkflowTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workflow_type: WorkflowTemplateType | None = None
    status: WorkflowTemplateStatus | None = None
    stages: list[WorkflowStage] | None = None
    default_required_checks: list[str] | None = None
    approval_gates: list[str] | None = None
    review_checklist: list[str] | None = None
    memory_capture_rules: list[str] | None = None
    recommended_models: list[str] | None = None
    tags: list[str] | None = None


class WorkflowTemplatePreview(BaseModel):
    template: "WorkflowTemplate"
    stages: list[WorkflowStage]
    required_checks: list[str]
    approval_gates: list[str]
    review_checklist: list[str]


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    slug: str
    description: str = ""
    workflow_type: WorkflowTemplateType = "custom"
    status: WorkflowTemplateStatus = "draft"
    stages: list[WorkflowStage] = []
    default_required_checks: list[str] = []
    approval_gates: list[str] = []
    review_checklist: list[str] = []
    memory_capture_rules: list[str] = []
    recommended_models: list[str] = []
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


WorkflowTemplatePreview.model_rebuild()
