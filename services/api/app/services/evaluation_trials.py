"""Project build trial framework (Release 10, Task 57).

Reporting / measurement layer for project-build trials. Does NOT run projects,
create workspaces, run OpenHands, or create branches/PRs. Callers (humans or
existing flows) drive the state machine via the API.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone

from ..models import (
    ProjectBuildTrial,
    ProjectBuildTrialCreate,
    ProjectBuildTrialStage,
    ProjectBuildTrialStageCreate,
    ProjectBuildTrialStageStatus,
    ProjectBuildTrialStageUpdate,
    ProjectBuildTrialStatus,
    ProjectBuildTrialSummary,
    ProjectBuildTrialUpdate,
    ProjectBuildTrialVerdict,
)
from ..repositories import (
    ProjectBuildTrialRepository,
    ProjectBuildTrialStageRepository,
)

_RUNNING_STATUSES = {"running"}


def create_trial(
    trial_repo: ProjectBuildTrialRepository,
    *,
    project_id: str,
    body: ProjectBuildTrialCreate,
) -> ProjectBuildTrial:
    now = datetime.now(timezone.utc)
    trial = ProjectBuildTrial(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=body.name,
        goal=body.goal,
        trial_type=body.trial_type,
        repository_id=body.repository_id,
        workspace_id=body.workspace_id,
        requirement_id=body.requirement_id,
        pr_draft_id=body.pr_draft_id,
        summary=body.summary,
        created_at=now,
        updated_at=now,
    )
    trial_repo.save(trial)
    return trial


def update_trial(
    trial_repo: ProjectBuildTrialRepository,
    trial: ProjectBuildTrial,
    body: ProjectBuildTrialUpdate,
) -> ProjectBuildTrial:
    data = trial.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    new_status = data.get("status")
    if (
        new_status in _RUNNING_STATUSES
        and trial.status not in _RUNNING_STATUSES
        and not data.get("started_at")
    ):
        data["started_at"] = datetime.now(timezone.utc)
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ProjectBuildTrial(**data)
    trial_repo.update(updated)
    return updated


def add_stage(
    stage_repo: ProjectBuildTrialStageRepository,
    *,
    project_id: str,
    trial_id: str,
    body: ProjectBuildTrialStageCreate,
) -> ProjectBuildTrialStage:
    now = datetime.now(timezone.utc)
    started_at = now if body.status == "running" else None
    completed_at = (
        now if body.status in {"passed", "failed", "skipped", "manual_fallback"} else None
    )
    stage = ProjectBuildTrialStage(
        id=str(uuid.uuid4()),
        project_id=project_id,
        trial_id=trial_id,
        name=body.name,
        stage_type=body.stage_type,
        status=body.status,
        evidence_summary=body.evidence_summary,
        linked_artifact_id=body.linked_artifact_id,
        linked_check_run_id=body.linked_check_run_id,
        linked_command_run_id=body.linked_command_run_id,
        linked_tool_run_id=body.linked_tool_run_id,
        linked_pr_review_id=body.linked_pr_review_id,
        linked_feedback_id=body.linked_feedback_id,
        notes=body.notes,
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
    )
    stage_repo.save(stage)
    return stage


def update_stage(
    stage_repo: ProjectBuildTrialStageRepository,
    stage: ProjectBuildTrialStage,
    body: ProjectBuildTrialStageUpdate,
) -> ProjectBuildTrialStage:
    data = stage.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    new_status = data.get("status")
    now = datetime.now(timezone.utc)
    if new_status == "running" and stage.status != "running" and not data.get("started_at"):
        data["started_at"] = now
    if new_status in {"passed", "failed", "skipped", "manual_fallback"} and not data.get(
        "completed_at"
    ):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = ProjectBuildTrialStage(**data)
    stage_repo.update(updated)
    return updated


def complete_trial(
    trial_repo: ProjectBuildTrialRepository,
    trial: ProjectBuildTrial,
    verdict: ProjectBuildTrialVerdict,
    summary: str | None = None,
    lessons_learned: str | None = None,
) -> ProjectBuildTrial:
    now = datetime.now(timezone.utc)
    new_status: ProjectBuildTrialStatus = (
        "completed" if verdict in {"pass", "pass_with_manual_fallback"} else "failed"
        if verdict == "fail"
        else "completed"
    )
    data = trial.model_dump()
    data["status"] = new_status
    data["verdict"] = verdict
    data["completed_at"] = now
    data["updated_at"] = now
    if summary is not None:
        data["summary"] = summary
    if lessons_learned is not None:
        data["lessons_learned"] = lessons_learned
    updated = ProjectBuildTrial(**data)
    trial_repo.update(updated)
    return updated


def build_summary(
    trial: ProjectBuildTrial,
    stages: list[ProjectBuildTrialStage],
) -> ProjectBuildTrialSummary:
    counts: dict[str, int] = dict(Counter(s.status for s in stages))
    for status in (
        "pending",
        "running",
        "passed",
        "failed",
        "skipped",
        "manual_fallback",
        "blocked",
    ):
        counts.setdefault(status, 0)
    return ProjectBuildTrialSummary(
        trial=trial,
        stage_counts=counts,
        total_stages=len(stages),
    )
