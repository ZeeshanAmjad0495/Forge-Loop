"""C1: Aider package preparation and result recording.

Parallel to ``openhands_workflow`` (one workflow per runner is the existing
repo pattern) so the OpenHands path is untouched and carries zero regression
risk. Reuses the shared code-repository resolver. The Aider runner is pure
(instruction package only); execution is independently gated.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from ..models import (
    Artifact,
    ToolRun,
    ToolRunnerDefinition,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    dev_task_repo,
    epic_repo,
    project_context_repo,
    project_repo,
    repo_safety_profile_repo,
    requirement_repo,
    tool_run_repo,
    tool_runner_definition_repo,
)
from ..tool_runners.aider import AiderRunner
from .openhands_workflow import resolve_code_repository

AIDER_RUNNER = AiderRunner()


def prepare_package(
    dev_task_id: str,
    tool_runner_definition_id: str | None,
    code_repository_id: str | None,
    current_user: str,
) -> ToolRun:
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    project = project_repo.get(dev_task.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    definition: ToolRunnerDefinition | None = None
    if tool_runner_definition_id is not None:
        definition = tool_runner_definition_repo.get(tool_runner_definition_id)
        if definition is None:
            raise HTTPException(
                status_code=404, detail="ToolRunnerDefinition not found"
            )
        if definition.runner_type != "aider":
            raise HTTPException(
                status_code=400,
                detail="ToolRunnerDefinition is not an Aider runner",
            )
        if not definition.enabled:
            raise HTTPException(
                status_code=400, detail="Aider runner definition is disabled"
            )

    code_repository = resolve_code_repository(
        dev_task.project_id, code_repository_id, definition
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

    package_dict = AIDER_RUNNER.prepare_run(
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
    package_content = json.dumps(package_dict, sort_keys=True)
    artifact_id = str(uuid.uuid4())
    artifact_repo.save(
        Artifact(
            id=artifact_id,
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="aider_instruction_package",
            content=package_content,
            created_at=now,
        )
    )
    run = ToolRun(
        id=str(uuid.uuid4()),
        project_id=project.id,
        code_repository_id=code_repository.id if code_repository else None,
        tool_runner_definition_id=definition.id if definition else None,
        target_type="dev_task",
        target_id=dev_task.id,
        runner_type="aider",
        mode="dry_run",
        status="completed",
        conclusion="requires_human_action",
        summary="Aider instruction package prepared",
        output=package_content,
        artifact_id=artifact_id,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    tool_run_repo.save(run)
    audit_writer.write(
        "aider_package_prepared",
        "tool_run",
        run.id,
        project_id=project.id,
        actor_email=current_user,
        details={
            "dev_task_id": dev_task.id,
            "tool_run_id": run.id,
            "code_repository_id": run.code_repository_id,
            "safety_profile_present": safety_profile is not None,
        },
    )
    return run


def record_result(
    tool_run_id: str,
    summary: str,
    output: str,
    conclusion,
    current_user: str,
) -> ToolRun:
    run = tool_run_repo.get(tool_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ToolRun not found")
    if run.runner_type != "aider":
        raise HTTPException(
            status_code=400, detail="ToolRun is not an Aider run"
        )
    updated = AIDER_RUNNER.record_result(
        tool_run=run,
        summary=summary,
        output=output,
        conclusion=conclusion,
    )
    tool_run_repo.save(updated)
    audit_writer.write(
        "aider_result_recorded",
        "tool_run",
        updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"tool_run_id": updated.id, "conclusion": updated.conclusion},
    )
    return updated
