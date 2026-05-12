from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ProjectTemplateType = Literal[
    "backend_api",
    "frontend_app",
    "full_stack_app",
    "cli_tool",
    "automation_tool",
    "ai_assistant",
    "data_pipeline",
    "qa_automation",
    "custom",
]
ProjectTemplateStatus = Literal[
    "draft",
    "active",
    "archived",
]


class ProjectTemplateCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    template_type: ProjectTemplateType = "custom"
    stack: list[str] = []
    tags: list[str] = []
    default_context: dict[str, Any] = {}
    suggested_required_checks: list[str] = []
    suggested_blocked_paths: list[str] = []
    suggested_workflows: list[str] = []
    file_manifest: list[str] = []
    instructions: str = ""
    status: ProjectTemplateStatus = "draft"


class ProjectTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template_type: ProjectTemplateType | None = None
    status: ProjectTemplateStatus | None = None
    stack: list[str] | None = None
    tags: list[str] | None = None
    default_context: dict[str, Any] | None = None
    suggested_required_checks: list[str] | None = None
    suggested_blocked_paths: list[str] | None = None
    suggested_workflows: list[str] | None = None
    file_manifest: list[str] | None = None
    instructions: str | None = None


class ProjectTemplatePreview(BaseModel):
    template: "ProjectTemplate"
    suggested_project_context: dict[str, Any]
    suggested_required_checks: list[str]
    suggested_blocked_paths: list[str]
    suggested_workflows: list[str]


class ProjectTemplate(BaseModel):
    id: str
    name: str
    slug: str
    description: str = ""
    template_type: ProjectTemplateType = "custom"
    status: ProjectTemplateStatus = "draft"
    stack: list[str] = []
    tags: list[str] = []
    default_context: dict[str, Any] = {}
    suggested_required_checks: list[str] = []
    suggested_blocked_paths: list[str] = []
    suggested_workflows: list[str] = []
    file_manifest: list[str] = []
    instructions: str = ""
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


ProjectTemplatePreview.model_rebuild()
