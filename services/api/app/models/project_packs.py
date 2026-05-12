from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ProjectPackDomain = Literal[
    "api_monitoring",
    "qa_automation",
    "web_scraping_reporting",
    "ai_assistant",
    "finance_tracker",
    "devtools",
    "automation",
    "content_tool",
    "custom",
]
ProjectPackStatus = Literal[
    "draft",
    "active",
    "archived",
]


class ProjectPackCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    domain: ProjectPackDomain = "custom"
    status: ProjectPackStatus = "draft"
    template_ids: list[str] = []
    workflow_template_ids: list[str] = []
    default_context: dict[str, Any] = {}
    suggested_memory: list[str] = []
    suggested_required_checks: list[str] = []
    suggested_blocked_paths: list[str] = []
    suggested_command_definitions: list[dict[str, Any]] = []
    suggested_budget_policy: dict[str, Any] = {}
    suggested_model_routing: dict[str, Any] = {}
    tags: list[str] = []


class ProjectPackUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: ProjectPackDomain | None = None
    status: ProjectPackStatus | None = None
    template_ids: list[str] | None = None
    workflow_template_ids: list[str] | None = None
    default_context: dict[str, Any] | None = None
    suggested_memory: list[str] | None = None
    suggested_required_checks: list[str] | None = None
    suggested_blocked_paths: list[str] | None = None
    suggested_command_definitions: list[dict[str, Any]] | None = None
    suggested_budget_policy: dict[str, Any] | None = None
    suggested_model_routing: dict[str, Any] | None = None
    tags: list[str] | None = None


class ProjectPackPreview(BaseModel):
    pack: "ProjectPack"
    suggested_project_context: dict[str, Any]
    suggested_required_checks: list[str]
    suggested_blocked_paths: list[str]
    suggested_memory: list[str]
    suggested_command_definitions: list[dict[str, Any]]
    suggested_budget_policy: dict[str, Any]
    suggested_model_routing: dict[str, Any]
    template_ids: list[str]
    workflow_template_ids: list[str]


class ProjectPack(BaseModel):
    id: str
    name: str
    slug: str
    description: str = ""
    domain: ProjectPackDomain = "custom"
    status: ProjectPackStatus = "draft"
    template_ids: list[str] = []
    workflow_template_ids: list[str] = []
    default_context: dict[str, Any] = {}
    suggested_memory: list[str] = []
    suggested_required_checks: list[str] = []
    suggested_blocked_paths: list[str] = []
    suggested_command_definitions: list[dict[str, Any]] = []
    suggested_budget_policy: dict[str, Any] = {}
    suggested_model_routing: dict[str, Any] = {}
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


ProjectPackPreview.model_rebuild()
