from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: str
    repo_url: str | None = None
    tech_stack: list[str] = []


class Project(BaseModel):
    id: str
    name: str
    description: str
    repo_url: str | None = None
    tech_stack: list[str] = []
    status: Literal["active"] = "active"
    created_at: datetime
    updated_at: datetime


class ProjectContextUpdate(BaseModel):
    architecture_notes: str = ""
    coding_standards: str = ""
    test_commands: str = ""
    deployment_commands: str = ""
    domain_rules: str = ""
    safety_rules: str = ""

    # B5: these fields are stored as strings, but callers naturally send
    # lists (e.g. test_commands=["pytest -q", "ruff check ."] or
    # domain_rules=[...]). Accept both: a list is joined with newlines so
    # downstream consumers still see a single string.
    @field_validator(
        "architecture_notes",
        "coding_standards",
        "test_commands",
        "deployment_commands",
        "domain_rules",
        "safety_rules",
        mode="before",
    )
    @classmethod
    def _coerce_list_to_str(cls, v: object) -> object:
        if isinstance(v, (list, tuple)):
            return "\n".join(str(x) for x in v)
        return v


class ProjectContext(ProjectContextUpdate):
    project_id: str
    updated_at: datetime | None = None
