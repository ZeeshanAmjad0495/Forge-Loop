import re as _re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    Artifact,
    ToolRun,
    ToolRunCreate,
    ToolRunnerDefinition,
    ToolRunnerDefinitionCreate,
    ToolRunnerDefinitionUpdate,
    ToolRunnerDefinitionsDefaultsRequest,
    ToolRunnerDefinitionsDefaultsResponse,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    code_repo_repo,
    project_repo,
    tool_run_repo,
    tool_runner_definition_repo,
)

router = APIRouter()


_SECRET_KEY_RE = _re.compile(r"(api[_-]?key|token|secret|password|credential)", _re.IGNORECASE)

_DEFAULT_RUNNER_TEMPLATES: list[dict] = [
    {
        "name": "OpenHands",
        "runner_type": "openhands",
        "mode": "dry_run",
        # Seeded enabled. Actual code execution is independently gated by
        # OPENHANDS_EXECUTION_ENABLED + the request mode, so enabling the
        # definition by default does not by itself run anything — it just
        # removes the surprising "prepare returns 'runner disabled'" step
        # every project hit on first use (B4).
        "enabled": True,
        "description": "Primary coding runner (OpenHands). Enabled by default; "
                       "execution still gated by OPENHANDS_EXECUTION_ENABLED.",
        "config": {},
    },
    {
        "name": "Manual Runner",
        "runner_type": "manual",
        "mode": "manual",
        "enabled": True,
        "description": "Records manual implementation work as tool run results.",
        "config": {},
    },
]


def _validate_config_no_secrets(config_dict: dict) -> None:
    """Raise 400 if any config key looks like a secret field."""
    for key in config_dict:
        if _SECRET_KEY_RE.search(key):
            raise HTTPException(
                status_code=400,
                detail=f"config key '{key}' looks like a secret field. "
                       "Store secrets via a secret provider, not in config.",
            )


def _suggested_runner_definitions(
    project_id: str,
    code_repository_id: str | None,
) -> list[ToolRunnerDefinition]:
    """Returns unsaved ToolRunnerDefinition instances for the default runner set."""
    now = datetime.now(timezone.utc)
    result: list[ToolRunnerDefinition] = []
    for tpl in _DEFAULT_RUNNER_TEMPLATES:
        result.append(
            ToolRunnerDefinition(
                id=str(uuid.uuid4()),
                project_id=project_id,
                code_repository_id=code_repository_id,
                name=tpl["name"],
                runner_type=tpl["runner_type"],  # type: ignore[arg-type]
                enabled=tpl["enabled"],
                mode=tpl["mode"],  # type: ignore[arg-type]
                description=tpl["description"],
                config=dict(tpl["config"]),
                created_at=now,
                updated_at=now,
            )
        )
    return result


@router.post(
    "/projects/{project_id}/tool-runner-definitions",
    response_model=ToolRunnerDefinition,
    status_code=201,
)
def create_tool_runner_definition(
    project_id: str,
    body: ToolRunnerDefinitionCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    _validate_config_no_secrets(body.config)
    now = datetime.now(timezone.utc)
    definition = ToolRunnerDefinition(
        id=str(uuid.uuid4()),
        project_id=project_id,
        code_repository_id=body.code_repository_id,
        name=body.name,
        runner_type=body.runner_type,
        enabled=body.enabled,
        mode=body.mode,
        description=body.description,
        config=body.config,
        created_at=now,
        updated_at=now,
    )
    tool_runner_definition_repo.save(definition)
    audit_writer.write(
        "tool_runner_definition_created", "tool_runner_definition", definition.id,
        project_id=project_id, actor_email=current_user,
        details={"runner_type": definition.runner_type, "name": definition.name, "source": "manual"},
    )
    return definition


@router.get(
    "/projects/{project_id}/tool-runner-definitions",
    response_model=list[ToolRunnerDefinition],
)
def list_project_tool_runner_definitions(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tool_runner_definition_repo.list_by_project(project_id)


@router.get("/tool-runner-definitions/{tool_runner_definition_id}", response_model=ToolRunnerDefinition)
def get_tool_runner_definition(tool_runner_definition_id: str, _: str = Depends(require_auth)):
    definition = tool_runner_definition_repo.get(tool_runner_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    return definition


@router.patch("/tool-runner-definitions/{tool_runner_definition_id}", response_model=ToolRunnerDefinition)
def update_tool_runner_definition(
    tool_runner_definition_id: str,
    body: ToolRunnerDefinitionUpdate,
    current_user: str = Depends(require_auth),
):
    definition = tool_runner_definition_repo.get(tool_runner_definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return definition
    if "config" in patch:
        _validate_config_no_secrets(patch["config"])
    updated = definition.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
    tool_runner_definition_repo.update(updated)
    audit_writer.write(
        "tool_runner_definition_updated", "tool_runner_definition", definition.id,
        project_id=definition.project_id, actor_email=current_user,
        details={"changed_fields": list(patch.keys())},
    )
    return updated


@router.post(
    "/projects/{project_id}/tool-runner-definitions/defaults",
    response_model=ToolRunnerDefinitionsDefaultsResponse,
    status_code=201,
)
def create_default_tool_runner_definitions(
    project_id: str,
    body: ToolRunnerDefinitionsDefaultsRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    code_repository_id: str | None = body.code_repository_id if body else None
    if code_repository_id is not None:
        if code_repo_repo.get(code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")

    candidates = _suggested_runner_definitions(project_id, code_repository_id)

    # Dedupe: (code_repository_id, runner_type, name) must be unique per project.
    existing_defs = tool_runner_definition_repo.list_by_project(project_id)
    existing_keys = {
        (d.code_repository_id, d.runner_type, d.name)
        for d in existing_defs
    }

    newly_created: list[ToolRunnerDefinition] = []
    already_existing: list[ToolRunnerDefinition] = []

    for candidate in candidates:
        key = (candidate.code_repository_id, candidate.runner_type, candidate.name)
        if key in existing_keys:
            match = next(
                (d for d in existing_defs if
                 d.code_repository_id == candidate.code_repository_id
                 and d.runner_type == candidate.runner_type
                 and d.name == candidate.name),
                None,
            )
            if match:
                already_existing.append(match)
        else:
            tool_runner_definition_repo.save(candidate)
            existing_keys.add(key)
            newly_created.append(candidate)
            audit_writer.write(
                "tool_runner_definition_created", "tool_runner_definition", candidate.id,
                project_id=project_id, actor_email=current_user,
                details={"runner_type": candidate.runner_type, "name": candidate.name, "source": "defaults"},
            )

    return ToolRunnerDefinitionsDefaultsResponse(
        created=newly_created,
        existing=already_existing,
    )


@router.post("/tool-runs", response_model=ToolRun, status_code=201)
def record_tool_run(
    body: ToolRunCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.code_repository_id is not None:
        if code_repo_repo.get(body.code_repository_id) is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
    if body.tool_runner_definition_id is not None:
        if tool_runner_definition_repo.get(body.tool_runner_definition_id) is None:
            raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
    now = datetime.now(timezone.utc)
    linked_artifact_id: str | None = None
    if body.output:
        linked_artifact_id = str(uuid.uuid4())
        artifact_repo.save(Artifact(
            id=linked_artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="tool_run_result",
            content=body.output,
            created_at=now,
        ))
    run = ToolRun(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        code_repository_id=body.code_repository_id,
        tool_runner_definition_id=body.tool_runner_definition_id,
        target_type=body.target_type,
        target_id=body.target_id,
        runner_type=body.runner_type,
        mode=body.mode,
        status=body.status,
        conclusion=body.conclusion,
        summary=body.summary,
        output=body.output,
        artifact_id=linked_artifact_id,
        started_at=body.started_at or now,
        completed_at=body.completed_at,
        created_at=now,
        updated_at=now,
    )
    tool_run_repo.save(run)
    audit_writer.write(
        "tool_run_recorded", "tool_run", run.id,
        project_id=body.project_id, actor_email=current_user,
        details={
            "runner_type": run.runner_type,
            "target_type": run.target_type,
            "target_id": run.target_id,
            "conclusion": run.conclusion,
            "tool_runner_definition_id": run.tool_runner_definition_id,
        },
    )
    return run


@router.get("/projects/{project_id}/tool-runs", response_model=list[ToolRun])
def list_project_tool_runs(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return tool_run_repo.list_by_project(project_id)


@router.get("/tool-runs/{tool_run_id}", response_model=ToolRun)
def get_tool_run(tool_run_id: str, _: str = Depends(require_auth)):
    run = tool_run_repo.get(tool_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ToolRun not found")
    return run
