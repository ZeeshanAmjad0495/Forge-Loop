import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    CodeRepository,
    CodeRepositoryCreate,
    CodeRepositoryUpdate,
    RepoSafetyProfile,
    RepoSafetyProfileUpsert,
)
from ..repositories_state import (
    audit_writer,
    code_repo_repo,
    project_repo,
    repo_safety_profile_repo,
)

router = APIRouter()


DEFAULT_ALLOWED_ACTIONS = ["read_code", "run_tests", "propose_changes"]
DEFAULT_BLOCKED_PATHS = [
    ".env",
    ".env.*",
    "secrets/",
    "credentials/",
    "terraform.tfstate",
    "infra/prod/",
]
DEFAULT_REQUIRED_CHECKS = ["tests", "build"]
DEFAULT_REQUIRES_APPROVAL_FOR = [
    "create_branch",
    "create_pr",
    "modify_infra",
    "update_dependencies",
    "delete_files",
    "deployment",
]
DEFAULT_PROTECTED_BRANCHES = ["main", "master"]
DEFAULT_WORK_SAFE_MODE = True


def default_safety_profile(repo_id: str, project_id: str) -> RepoSafetyProfile:
    now = datetime.now(timezone.utc)
    return RepoSafetyProfile(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=repo_id,
        work_safe_mode=DEFAULT_WORK_SAFE_MODE,
        allowed_actions=list(DEFAULT_ALLOWED_ACTIONS),
        blocked_paths=list(DEFAULT_BLOCKED_PATHS),
        required_checks=list(DEFAULT_REQUIRED_CHECKS),
        requires_approval_for=list(DEFAULT_REQUIRES_APPROVAL_FOR),
        protected_branches=list(DEFAULT_PROTECTED_BRANCHES),
        notes="",
        created_at=now,
        updated_at=now,
    )


@router.post("/projects/{project_id}/code-repositories", response_model=CodeRepository, status_code=201)
def create_code_repository(
    project_id: str,
    body: CodeRepositoryCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.now(timezone.utc)
    repo_obj = CodeRepository(
        id=str(uuid.uuid4()),
        project_id=project_id,
        provider=body.provider,
        repo_url=body.repo_url,
        name=body.name,
        default_branch=body.default_branch,
        status="active",
        created_at=now,
        updated_at=now,
    )
    code_repo_repo.save(repo_obj)
    audit_writer.write(
        "code_repository_created",
        "code_repository",
        repo_obj.id,
        project_id=project_id,
        actor_email=current_user,
        details={"provider": repo_obj.provider, "repo_url": repo_obj.repo_url},
    )
    return repo_obj


@router.get("/projects/{project_id}/code-repositories", response_model=list[CodeRepository])
def list_project_code_repositories(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return code_repo_repo.list_by_project(project_id)


@router.get("/code-repositories/{repo_id}", response_model=CodeRepository)
def get_code_repository(repo_id: str, _: str = Depends(require_auth)):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    return repo_obj


@router.patch("/code-repositories/{repo_id}", response_model=CodeRepository)
def update_code_repository(
    repo_id: str,
    body: CodeRepositoryUpdate,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    changed_fields = [k for k, v in body.model_dump(exclude_unset=True).items() if v is not None]
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc)
    updated = repo_obj.model_copy(update=updates)
    code_repo_repo.update(updated)
    audit_writer.write(
        "code_repository_updated",
        "code_repository",
        repo_obj.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"changed_fields": changed_fields},
    )
    return updated


@router.post("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def upsert_repo_safety_profile(
    repo_id: str,
    body: RepoSafetyProfileUpsert,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    now = datetime.now(timezone.utc)
    profile_id = existing.id if existing else str(uuid.uuid4())
    created_at = existing.created_at if existing else now
    status_code = 200 if existing else 201
    profile = RepoSafetyProfile(
        id=profile_id,
        project_id=repo_obj.project_id,
        code_repository_id=repo_id,
        work_safe_mode=body.work_safe_mode,
        allowed_actions=body.allowed_actions,
        blocked_paths=body.blocked_paths,
        required_checks=body.required_checks,
        requires_approval_for=body.requires_approval_for,
        protected_branches=body.protected_branches,
        notes=body.notes,
        created_at=created_at,
        updated_at=now,
    )
    repo_safety_profile_repo.save(profile)
    audit_writer.write(
        "repo_safety_profile_updated",
        "repo_safety_profile",
        profile.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"code_repository_id": repo_id},
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(content=profile.model_dump(mode="json"), status_code=status_code)


@router.get("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def get_repo_safety_profile(repo_id: str, _: str = Depends(require_auth)):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    if existing:
        return existing
    return default_safety_profile(repo_id, repo_obj.project_id)


@router.patch("/code-repositories/{repo_id}/safety-profile", response_model=RepoSafetyProfile)
def patch_repo_safety_profile(
    repo_id: str,
    body: RepoSafetyProfileUpsert,
    current_user: str = Depends(require_auth),
):
    repo_obj = code_repo_repo.get(repo_id)
    if repo_obj is None:
        raise HTTPException(status_code=404, detail="CodeRepository not found")
    existing = repo_safety_profile_repo.get_by_repo(repo_id)
    base = existing if existing else default_safety_profile(repo_id, repo_obj.project_id)
    now = datetime.now(timezone.utc)
    patch_data = body.model_dump(exclude_unset=True)
    updated = base.model_copy(update={**patch_data, "updated_at": now})
    if not existing:
        updated = updated.model_copy(update={"created_at": now})
    repo_safety_profile_repo.save(updated)
    audit_writer.write(
        "repo_safety_profile_updated",
        "repo_safety_profile",
        updated.id,
        project_id=repo_obj.project_id,
        actor_email=current_user,
        details={"code_repository_id": repo_id},
    )
    return updated
