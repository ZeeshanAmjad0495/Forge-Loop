import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    CheckDefinition,
    CheckDefinitionCreate,
    CheckDefinitionUpdate,
    CheckDefinitionsFromSafetyProfileRequest,
    CheckDefinitionsFromSafetyProfileResponse,
    CheckRun,
    CheckRunCreate,
    CheckType,
    RepoSafetyProfile,
)
from ..repositories_state import (
    audit_writer,
    check_definition_repo,
    check_run_repo,
    code_repo_repo,
    project_repo,
    repo_safety_profile_repo,
)
from .code_repositories import DEFAULT_REQUIRED_CHECKS

router = APIRouter()


_CHECK_MAP: dict[str, tuple[CheckType, str, str]] = {
    "tests":      ("tests",           "Tests",                 "pytest"),
    "build":      ("build",           "Build",                 "npm run build"),
    "lint":       ("lint",            "Lint",                  ""),
    "typecheck":  ("typecheck",       "Typecheck",             ""),
    "coverage":   ("coverage",        "Coverage",              ""),
    "semgrep":    ("security_sast",   "Semgrep SAST",          "semgrep scan"),
    "osv":        ("dependency_scan", "OSV dependency scan",   "osv-scanner"),
    "trivy":      ("container_scan",  "Trivy container scan",  "trivy"),
    "gitleaks":   ("secret_scan",     "Gitleaks secret scan",  "gitleaks detect"),
    "axe":        ("accessibility",   "axe accessibility",     ""),
    "playwright": ("e2e",             "Playwright e2e",        ""),
}


def _suggested_definitions(
    required_checks: list[str],
    project_id: str,
    code_repository_id: str | None,
) -> list[CheckDefinition]:
    """Pure helper: returns unsaved CheckDefinition instances for recognized keys."""
    now = datetime.now(timezone.utc)
    result: list[CheckDefinition] = []
    for key in required_checks:
        mapping = _CHECK_MAP.get(key)
        if mapping is None:
            continue
        check_type, name, command = mapping
        result.append(
            CheckDefinition(
                id=str(uuid.uuid4()),
                project_id=project_id,
                code_repository_id=code_repository_id,
                name=name,
                check_type=check_type,
                command=command,
                required=True,
                enabled=True,
                severity="blocking",
                description="",
                created_at=now,
                updated_at=now,
            )
        )
    return result


@router.post(
    "/projects/{project_id}/check-definitions",
    response_model=CheckDefinition,
    status_code=201,
)
def create_check_definition(
    project_id: str,
    body: CheckDefinitionCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    now = datetime.now(timezone.utc)
    definition = CheckDefinition(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        name=body.name,
        check_type=body.check_type,
        command=body.command,
        required=body.required,
        enabled=body.enabled,
        severity=body.severity,
        description=body.description,
        created_at=now,
        updated_at=now,
    )
    check_definition_repo.save(definition)
    audit_writer.write(
        "check_definition_created", "check_definition", definition.id,
        project_id=project_id, actor_email=current_user,
        details={"check_type": definition.check_type, "name": definition.name},
    )
    return definition


@router.get("/projects/{project_id}/check-definitions", response_model=list[CheckDefinition])
def list_project_check_definitions(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_definition_repo.list_by_project(project_id)


@router.get("/check-definitions/{check_definition_id}", response_model=CheckDefinition)
def get_check_definition(check_definition_id: str, _: str = Depends(require_auth)):
    definition = check_definition_repo.get(check_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    return definition


@router.patch("/check-definitions/{check_definition_id}", response_model=CheckDefinition)
def update_check_definition(
    check_definition_id: str,
    body: CheckDefinitionUpdate,
    current_user: str = Depends(require_auth),
):
    definition = check_definition_repo.get(check_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return definition
    updated = definition.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    check_definition_repo.update(updated)
    audit_writer.write(
        "check_definition_updated", "check_definition", definition.id,
        project_id=definition.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated


@router.post(
    "/projects/{project_id}/check-definitions/from-safety-profile",
    response_model=CheckDefinitionsFromSafetyProfileResponse,
    status_code=201,
)
def create_check_definitions_from_safety_profile(
    project_id: str,
    body: CheckDefinitionsFromSafetyProfileRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    code_repository_id: str | None = body.code_repository_id if body else None
    if code_repository_id is not None:
        if code_repo_repo.get(code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")

    # Resolve required_checks: use saved safety profile if available, else defaults.
    profile: RepoSafetyProfile | None = None
    if code_repository_id is not None:
        profile = repo_safety_profile_repo.get_by_repo(code_repository_id)
    required_checks = profile.required_checks if profile is not None else list(DEFAULT_REQUIRED_CHECKS)

    candidates = _suggested_definitions(required_checks, project_id, code_repository_id)

    # Dedupe: (code_repository_id, check_type, name) must be unique per project.
    existing_defs = check_definition_repo.list_by_project(project_id)
    existing_keys = {
        (d.code_repository_id, d.check_type, d.name)
        for d in existing_defs
    }

    newly_created: list[CheckDefinition] = []
    already_existing: list[CheckDefinition] = []

    for candidate in candidates:
        key = (candidate.code_repository_id, candidate.check_type, candidate.name)
        if key in existing_keys:
            # Find the matching existing definition to return it.
            match = next(
                (d for d in existing_defs if
                 d.code_repository_id == candidate.code_repository_id
                 and d.check_type == candidate.check_type
                 and d.name == candidate.name),
                None,
            )
            if match:
                already_existing.append(match)
        else:
            check_definition_repo.save(candidate)
            existing_keys.add(key)
            newly_created.append(candidate)
            audit_writer.write(
                "check_definition_created", "check_definition", candidate.id,
                project_id=project_id, actor_email=current_user,
                details={"check_type": candidate.check_type, "name": candidate.name, "source": "safety_profile"},
            )

    return CheckDefinitionsFromSafetyProfileResponse(
        created=newly_created,
        existing=already_existing,
    )


@router.post("/check-runs", response_model=CheckRun, status_code=201)
def record_check_run(
    body: CheckRunCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.check_definition_id is not None:
        if check_definition_repo.get(body.check_definition_id) is None:
            raise HTTPException(status_code=404, detail="CheckDefinition not found")
    now = datetime.now(timezone.utc)
    run = CheckRun(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        code_repository_id=body.code_repository_id,
        check_definition_id=body.check_definition_id,
        target_type=body.target_type,
        target_id=body.target_id,
        status=body.status,
        conclusion=body.conclusion,
        summary=body.summary,
        output=body.output,
        artifact_id=None,
        started_at=body.started_at or now,
        completed_at=body.completed_at,
        created_at=now,
        updated_at=now,
    )
    check_run_repo.save(run)
    audit_writer.write(
        "check_run_recorded", "check_run", run.id,
        project_id=body.project_id, actor_email=current_user,
        details={
            "target_type": run.target_type,
            "target_id": run.target_id,
            "conclusion": run.conclusion,
            "check_definition_id": run.check_definition_id,
        },
    )
    return run


@router.get("/projects/{project_id}/check-runs", response_model=list[CheckRun])
def list_project_check_runs(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return check_run_repo.list_by_project(project_id)


@router.get("/check-runs/{check_run_id}", response_model=CheckRun)
def get_check_run(check_run_id: str, _: str = Depends(require_auth)):
    run = check_run_repo.get(check_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="CheckRun not found")
    return run
