from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CodeRepositoryProvider = Literal["github", "gitlab", "bitbucket", "other"]
CodeRepositoryStatus = Literal["active", "disabled"]


class CodeRepositoryCreate(BaseModel):
    provider: CodeRepositoryProvider = "github"
    repo_url: str
    name: str
    default_branch: str = "main"


class CodeRepositoryUpdate(BaseModel):
    provider: CodeRepositoryProvider | None = None
    repo_url: str | None = None
    name: str | None = None
    default_branch: str | None = None
    status: CodeRepositoryStatus | None = None


class CodeRepository(BaseModel):
    id: str
    project_id: str
    provider: CodeRepositoryProvider
    repo_url: str
    name: str
    default_branch: str
    status: CodeRepositoryStatus = "active"
    created_at: datetime
    updated_at: datetime


class RepoSafetyProfileUpsert(BaseModel):
    work_safe_mode: bool = True
    allowed_actions: list[str] = []
    blocked_paths: list[str] = []
    required_checks: list[str] = []
    requires_approval_for: list[str] = []
    protected_branches: list[str] = []
    notes: str = ""


class RepoSafetyProfile(BaseModel):
    id: str
    project_id: str
    code_repository_id: str
    work_safe_mode: bool
    allowed_actions: list[str]
    blocked_paths: list[str]
    required_checks: list[str]
    requires_approval_for: list[str]
    protected_branches: list[str]
    notes: str
    created_at: datetime
    updated_at: datetime
