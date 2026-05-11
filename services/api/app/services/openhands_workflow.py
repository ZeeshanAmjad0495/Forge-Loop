"""OpenHands package preparation and result recording.

Owns the two `openhands_*` audit events and the `OpenHandsRunner`
singleton. `tool_runners/openhands.py` remains the adapter/runner
boundary.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from .. import config as _config
from ..models import (
    OpenHandsInstructionPackage,
    OpenHandsPreparePackageRequest,
    OpenHandsPrepareResponse,
    OpenHandsRecordResultRequest,
    ToolRun,
    ToolRunnerDefinition,
)
from ..repositories_state import (
    audit_writer,
    code_repo_repo,
    dev_task_repo,
    epic_repo,
    project_context_repo,
    project_repo,
    repo_safety_profile_repo,
    requirement_repo,
    tool_run_repo,
    tool_runner_definition_repo,
)
from ..tool_runners.openhands import OpenHandsRunner

OPENHANDS_RUNNER = OpenHandsRunner()


def resolve_code_repository(
    project_id: str,
    requested_repo_id: str | None,
    definition: ToolRunnerDefinition | None,
):
    """Resolve a CodeRepository for the OpenHands package, or None.

    Precedence: explicit request > definition.code_repository_id > sole project repo.
    Raises 404 if a requested id is missing.
    """
    repo_id = requested_repo_id or (definition.code_repository_id if definition else None)
    if repo_id is not None:
        cr = code_repo_repo.get(repo_id)
        if cr is None:
            raise HTTPException(status_code=404, detail="CodeRepository not found")
        if cr.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="CodeRepository does not belong to dev task's project",
            )
        return cr
    project_repos = code_repo_repo.list_by_project(project_id)
    if len(project_repos) == 1:
        return project_repos[0]
    return None


def prepare_package(
    dev_task_id: str,
    body: OpenHandsPreparePackageRequest | None,
    current_user: str,
) -> OpenHandsPrepareResponse:
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    project = project_repo.get(dev_task.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    body = body or OpenHandsPreparePackageRequest()

    definition: ToolRunnerDefinition | None = None
    if body.tool_runner_definition_id is not None:
        definition = tool_runner_definition_repo.get(body.tool_runner_definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="ToolRunnerDefinition not found")
        if definition.runner_type != "openhands":
            raise HTTPException(
                status_code=400,
                detail="ToolRunnerDefinition is not an OpenHands runner",
            )
        if not definition.enabled:
            raise HTTPException(
                status_code=400,
                detail="OpenHands runner definition is disabled",
            )

    if _config.OPENHANDS_MODE not in ("dry_run", "manual") and not _config.OPENHANDS_EXECUTION_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="OpenHands execution is disabled (OPENHANDS_EXECUTION_ENABLED=false)",
        )

    code_repository = resolve_code_repository(
        dev_task.project_id, body.code_repository_id, definition
    )
    safety_profile = (
        repo_safety_profile_repo.get_by_repo(code_repository.id)
        if code_repository is not None
        else None
    )
    project_context = project_context_repo.get(project.id)

    requirement_summary: str | None = None
    if dev_task.requirement_id:
        req = requirement_repo.get(dev_task.requirement_id)
        if req is not None:
            requirement_summary = req.problem_statement or req.title

    epic_title: str | None = None
    if dev_task.epic_id:
        epic = epic_repo.get(dev_task.epic_id)
        if epic is not None:
            epic_title = epic.title

    package_dict = OPENHANDS_RUNNER.prepare_run(
        project=project,
        dev_task=dev_task,
        code_repository=code_repository,
        safety_profile=safety_profile,
        project_context=project_context,
        definition=definition,
        requirement_summary=requirement_summary,
        epic_title=epic_title,
    )

    now = datetime.now(timezone.utc)
    run = ToolRun(
        id=str(uuid.uuid4()),
        project_id=project.id,
        code_repository_id=code_repository.id if code_repository is not None else None,
        tool_runner_definition_id=definition.id if definition is not None else None,
        target_type="dev_task",
        target_id=dev_task.id,
        runner_type="openhands",
        mode="dry_run",
        status="completed",
        conclusion="requires_human_action",
        summary="OpenHands instruction package prepared",
        output=json.dumps(package_dict, sort_keys=True),
        artifact_id=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    tool_run_repo.save(run)
    audit_writer.write(
        "openhands_package_prepared", "tool_run", run.id,
        project_id=project.id, actor_email=current_user,
        details={
            "dev_task_id": dev_task.id,
            "tool_run_id": run.id,
            "code_repository_id": run.code_repository_id,
            "safety_profile_present": safety_profile is not None,
        },
    )
    return OpenHandsPrepareResponse(
        tool_run=run,
        instruction_package=OpenHandsInstructionPackage(**package_dict),
    )


def record_result(
    tool_run_id: str,
    body: OpenHandsRecordResultRequest,
    current_user: str,
) -> ToolRun:
    run = tool_run_repo.get(tool_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ToolRun not found")
    if run.runner_type != "openhands":
        raise HTTPException(
            status_code=400,
            detail="ToolRun is not an OpenHands run",
        )
    updated = OPENHANDS_RUNNER.record_result(
        tool_run=run,
        summary=body.summary,
        output=body.output,
        conclusion=body.conclusion,
    )
    tool_run_repo.save(updated)
    audit_writer.write(
        "openhands_result_recorded", "tool_run", updated.id,
        project_id=updated.project_id, actor_email=current_user,
        details={"tool_run_id": updated.id, "conclusion": updated.conclusion},
    )
    return updated
