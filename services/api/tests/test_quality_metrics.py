import uuid
from datetime import datetime, timezone

from app.models import (
    CheckRun,
    CommandRun,
    ProjectBuildTrialCreate,
    ProjectBuildTrialStageCreate,
    ProjectMemoryCandidate,
    ReviewFeedback,
    ToolRun,
)
from app.repositories_state import (
    check_run_repo,
    command_run_repo,
    memory_candidate_repo,
    project_build_trial_repo,
    project_build_trial_stage_repo,
    review_feedback_repo,
    tool_run_repo,
)
from app.services.evaluation_trials import add_stage, create_trial


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_run(project_id: str, conclusion: str = "success") -> CheckRun:
    return CheckRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        check_definition_id="cd",
        target_type="dev_task",
        target_id="t",
        status="completed",
        conclusion=conclusion,  # type: ignore[arg-type]
        summary="",
        started_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )


def _command_run(project_id: str, conclusion: str = "success") -> CommandRun:
    return CommandRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        workspace_id="w",
        target_type="manual",
        target_id="x",
        command="pytest",
        args=[],
        status="completed",
        conclusion=conclusion,  # type: ignore[arg-type]
        exit_code=0,
        created_at=_now(),
        updated_at=_now(),
    )


def _tool_run(project_id: str, conclusion: str = "success") -> ToolRun:
    return ToolRun(
        id=str(uuid.uuid4()),
        project_id=project_id,
        runner_type="manual",
        mode="manual",
        target_type="manual",
        target_id="x",
        status="completed",
        conclusion=conclusion,  # type: ignore[arg-type]
        started_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )


def _feedback(project_id: str, severity: str = "blocking", status: str = "open") -> ReviewFeedback:
    return ReviewFeedback(
        id=str(uuid.uuid4()),
        project_id=project_id,
        pr_draft_id="d",
        source="human",
        severity=severity,  # type: ignore[arg-type]
        category="correctness",
        status=status,  # type: ignore[arg-type]
        summary="x",
        created_at=_now(),
        updated_at=_now(),
    )


def _candidate(project_id: str, status: str = "approved") -> ProjectMemoryCandidate:
    return ProjectMemoryCandidate(
        id=str(uuid.uuid4()),
        project_id=project_id,
        memory_type="project_rule",
        title="t",
        content="c",
        tags=[],
        status=status,  # type: ignore[arg-type]
        source_type="manual",
        source_id=None,
        created_at=_now(),
        updated_at=_now(),
    )


def test_project_metrics_endpoint_empty(client, project):
    res = client.get(f"/projects/{project['id']}/quality-metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["metrics"]["total_stages"] == 0
    assert body["metrics"]["total_check_runs"] == 0


def test_project_metrics_endpoint_unknown_project(client):
    res = client.get("/projects/missing/quality-metrics")
    assert res.status_code == 404


def test_project_metrics_counts_runs_and_feedback(client, project):
    project_id = project["id"]
    check_run_repo.save(_check_run(project_id, "success"))
    check_run_repo.save(_check_run(project_id, "failure"))
    command_run_repo.save(_command_run(project_id, "success"))
    tool_run_repo.save(_tool_run(project_id, "failure"))
    review_feedback_repo.save(_feedback(project_id, severity="blocking"))
    review_feedback_repo.save(_feedback(project_id, severity="info", status="resolved"))
    memory_candidate_repo.save(_candidate(project_id, status="approved"))
    memory_candidate_repo.save(_candidate(project_id, status="proposed"))

    res = client.get(f"/projects/{project_id}/quality-metrics").json()
    m = res["metrics"]
    assert m["total_check_runs"] == 2
    assert m["successful_check_runs"] == 1
    assert m["failed_check_runs"] == 1
    assert m["total_command_runs"] == 1
    assert m["total_tool_runs"] == 1
    assert m["failed_tool_runs"] == 1
    assert m["feedback_items_count"] == 2
    assert m["blocking_feedback_count"] == 1
    assert m["resolved_feedback_count"] == 1
    assert m["memory_candidates_created"] == 2
    assert m["memory_candidates_approved"] == 1


def test_trial_metrics_endpoint(client, project):
    project_id = project["id"]
    trial = create_trial(
        project_build_trial_repo,
        project_id=project_id,
        body=ProjectBuildTrialCreate(name="t"),
    )
    add_stage(
        project_build_trial_stage_repo,
        project_id=project_id,
        trial_id=trial.id,
        body=ProjectBuildTrialStageCreate(
            name="setup", stage_type="setup", status="passed"
        ),
    )
    add_stage(
        project_build_trial_stage_repo,
        project_id=project_id,
        trial_id=trial.id,
        body=ProjectBuildTrialStageCreate(
            name="check",
            stage_type="check",
            status="failed",
            linked_check_run_id="cr-1",
        ),
    )
    res = client.get(f"/build-trials/{trial.id}/quality-metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["trial_id"] == trial.id
    assert body["metrics"]["total_stages"] == 2
    assert body["metrics"]["passed_stages"] == 1
    assert body["metrics"]["failed_stages"] == 1
    assert body["metrics"]["total_check_runs"] == 1


def test_trial_metrics_unknown_trial(client):
    res = client.get("/build-trials/missing/quality-metrics")
    assert res.status_code == 404


def test_snapshot_trial_metrics(client, project):
    project_id = project["id"]
    trial = create_trial(
        project_build_trial_repo,
        project_id=project_id,
        body=ProjectBuildTrialCreate(name="t"),
    )
    res = client.post(f"/build-trials/{trial.id}/quality-metrics/snapshot")
    assert res.status_code == 201
    body = res.json()
    assert body["project_id"] == project_id
    assert body["trial_id"] == trial.id
    assert "total_stages" in body["metrics"]
