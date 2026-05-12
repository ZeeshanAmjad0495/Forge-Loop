"""Quality metrics foundation (Release 10, Task 58).

Calculates simple counters for a project (or a specific build trial) from
existing repositories. MVP-grade: counters only, no charts, no aggregation
jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    ProjectBuildTrial,
    ProjectBuildTrialStage,
    QualityMetricSnapshot,
)
from ..repositories import (
    CheckRunRepository,
    CommandRunRepository,
    ProjectBuildTrialRepository,
    ProjectBuildTrialStageRepository,
    ProjectMemoryCandidateRepository,
    PullRequestDraftRepository,
    PullRequestReviewRepository,
    QualityMetricSnapshotRepository,
    ReviewFeedbackRepository,
    ToolRunRepository,
)


def _count_stage_statuses(stages: list[ProjectBuildTrialStage]) -> dict[str, int]:
    counts = {
        "total_stages": len(stages),
        "passed_stages": 0,
        "failed_stages": 0,
        "skipped_stages": 0,
        "manual_fallback_stages": 0,
    }
    for s in stages:
        if s.status == "passed":
            counts["passed_stages"] += 1
        elif s.status == "failed":
            counts["failed_stages"] += 1
        elif s.status == "skipped":
            counts["skipped_stages"] += 1
        elif s.status == "manual_fallback":
            counts["manual_fallback_stages"] += 1
    return counts


def _success_failure_counts(
    items: list, *, success_value: str = "success", failure_value: str = "failure"
) -> tuple[int, int]:
    success = sum(1 for i in items if getattr(i, "conclusion", None) == success_value)
    failure = sum(1 for i in items if getattr(i, "conclusion", None) == failure_value)
    return success, failure


def calculate_project_metrics(
    *,
    project_id: str,
    check_run_repo: CheckRunRepository,
    command_run_repo: CommandRunRepository,
    tool_run_repo: ToolRunRepository,
    pr_review_repo: PullRequestReviewRepository,
    review_feedback_repo: ReviewFeedbackRepository,
    memory_candidate_repo: ProjectMemoryCandidateRepository,
    project_build_trial_repo: ProjectBuildTrialRepository,
    project_build_trial_stage_repo: ProjectBuildTrialStageRepository,
    pr_draft_repo: PullRequestDraftRepository | None = None,
) -> dict:
    check_runs = check_run_repo.list_by_project(project_id)
    command_runs = command_run_repo.list_by_project(project_id)
    tool_runs = tool_run_repo.list_by_project(project_id)
    feedback = review_feedback_repo.list_by_project(project_id)
    memory_candidates = memory_candidate_repo.list_by_project(project_id)
    trials = project_build_trial_repo.list_by_project(project_id)

    # Aggregate stages across all trials (kept cheap — trials are few).
    all_stages: list[ProjectBuildTrialStage] = []
    for t in trials:
        all_stages.extend(project_build_trial_stage_repo.list_by_trial(t.id))

    # PR reviews: derive via the project's PR drafts.
    pr_reviews_count = 0
    if pr_draft_repo is not None:
        drafts = pr_draft_repo.list_by_project(project_id)
        for draft in drafts:
            pr_reviews_count += len(pr_review_repo.list_by_pr_draft(draft.id))

    check_success, check_failure = _success_failure_counts(check_runs)
    cmd_success, cmd_failure = _success_failure_counts(command_runs)
    tool_success, tool_failure = _success_failure_counts(tool_runs)

    blocking_feedback = sum(1 for f in feedback if getattr(f, "severity", None) == "blocking")
    resolved_feedback = sum(1 for f in feedback if getattr(f, "status", None) == "resolved")

    candidates_created = len(memory_candidates)
    candidates_approved = sum(1 for c in memory_candidates if c.status == "approved")

    metrics = _count_stage_statuses(all_stages)
    metrics.update(
        {
            "total_check_runs": len(check_runs),
            "successful_check_runs": check_success,
            "failed_check_runs": check_failure,
            "total_command_runs": len(command_runs),
            "successful_command_runs": cmd_success,
            "failed_command_runs": cmd_failure,
            "total_tool_runs": len(tool_runs),
            "successful_tool_runs": tool_success,
            "failed_tool_runs": tool_failure,
            "pr_reviews_count": pr_reviews_count,
            "feedback_items_count": len(feedback),
            "blocking_feedback_count": blocking_feedback,
            "resolved_feedback_count": resolved_feedback,
            "memory_candidates_created": candidates_created,
            "memory_candidates_approved": candidates_approved,
            "total_trials": len(trials),
        }
    )
    return metrics


def calculate_trial_metrics(
    *,
    trial: ProjectBuildTrial,
    check_run_repo: CheckRunRepository,
    command_run_repo: CommandRunRepository,
    tool_run_repo: ToolRunRepository,
    review_feedback_repo: ReviewFeedbackRepository,
    project_build_trial_stage_repo: ProjectBuildTrialStageRepository,
) -> dict:
    stages = project_build_trial_stage_repo.list_by_trial(trial.id)
    metrics = _count_stage_statuses(stages)

    # For trial-scoped metrics we count linked-run IDs as success/failure
    # signals where available. Lightweight; no joins.
    linked_check_ids = {s.linked_check_run_id for s in stages if s.linked_check_run_id}
    linked_cmd_ids = {s.linked_command_run_id for s in stages if s.linked_command_run_id}
    linked_tool_ids = {s.linked_tool_run_id for s in stages if s.linked_tool_run_id}
    linked_pr_review_ids = {s.linked_pr_review_id for s in stages if s.linked_pr_review_id}
    linked_feedback_ids = {s.linked_feedback_id for s in stages if s.linked_feedback_id}

    metrics.update(
        {
            "total_check_runs": len(linked_check_ids),
            "total_command_runs": len(linked_cmd_ids),
            "total_tool_runs": len(linked_tool_ids),
            "pr_reviews_count": len(linked_pr_review_ids),
            "feedback_items_count": len(linked_feedback_ids),
        }
    )
    return metrics


def create_snapshot(
    snapshot_repo: QualityMetricSnapshotRepository,
    *,
    project_id: str,
    metrics: dict,
    trial_id: str | None = None,
    source_type: str = "project",
    source_id: str | None = None,
    summary: str | None = None,
) -> QualityMetricSnapshot:
    now = datetime.now(timezone.utc)
    snap = QualityMetricSnapshot(
        id=str(uuid.uuid4()),
        project_id=project_id,
        trial_id=trial_id,
        source_type=source_type,
        source_id=source_id,
        metrics=dict(metrics),
        summary=summary,
        created_at=now,
        updated_at=now,
    )
    snapshot_repo.save(snap)
    return snap
