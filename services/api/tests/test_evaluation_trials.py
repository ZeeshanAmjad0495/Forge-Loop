from app.models import (
    ProjectBuildTrialCreate,
    ProjectBuildTrialStageCreate,
    ProjectBuildTrialStageUpdate,
    ProjectBuildTrialUpdate,
)
from app.repositories import (
    InMemoryProjectBuildTrialRepository,
    InMemoryProjectBuildTrialStageRepository,
)
from app.services.evaluation_trials import (
    add_stage,
    build_summary,
    complete_trial,
    create_trial,
    update_stage,
    update_trial,
)


# -- service unit tests ----------------------------------------------------


def test_create_trial_persists_defaults():
    repo = InMemoryProjectBuildTrialRepository()
    trial = create_trial(
        repo,
        project_id="p1",
        body=ProjectBuildTrialCreate(name="trial-1", goal="g"),
    )
    assert trial.project_id == "p1"
    assert trial.status == "planned"
    assert trial.verdict == "not_evaluated"
    assert repo.get(trial.id) == trial


def test_update_trial_running_sets_started_at():
    repo = InMemoryProjectBuildTrialRepository()
    trial = create_trial(
        repo, project_id="p1", body=ProjectBuildTrialCreate(name="t")
    )
    assert trial.started_at is None
    updated = update_trial(repo, trial, ProjectBuildTrialUpdate(status="running"))
    assert updated.status == "running"
    assert updated.started_at is not None


def test_add_stage_passed_sets_completed_at():
    repo = InMemoryProjectBuildTrialStageRepository()
    stage = add_stage(
        repo,
        project_id="p1",
        trial_id="t1",
        body=ProjectBuildTrialStageCreate(
            name="setup", stage_type="setup", status="passed"
        ),
    )
    assert stage.status == "passed"
    assert stage.completed_at is not None


def test_update_stage_running_sets_started_at():
    repo = InMemoryProjectBuildTrialStageRepository()
    stage = add_stage(
        repo,
        project_id="p1",
        trial_id="t1",
        body=ProjectBuildTrialStageCreate(name="s", stage_type="setup"),
    )
    assert stage.started_at is None
    updated = update_stage(
        repo, stage, ProjectBuildTrialStageUpdate(status="running")
    )
    assert updated.started_at is not None


def test_complete_trial_sets_completed_status_and_verdict():
    trial_repo = InMemoryProjectBuildTrialRepository()
    trial = create_trial(
        trial_repo, project_id="p1", body=ProjectBuildTrialCreate(name="t")
    )
    completed = complete_trial(
        trial_repo, trial, verdict="pass", summary="ok", lessons_learned="lessons"
    )
    assert completed.status == "completed"
    assert completed.verdict == "pass"
    assert completed.summary == "ok"
    assert completed.lessons_learned == "lessons"
    assert completed.completed_at is not None


def test_complete_trial_failure_sets_failed_status():
    trial_repo = InMemoryProjectBuildTrialRepository()
    trial = create_trial(
        trial_repo, project_id="p1", body=ProjectBuildTrialCreate(name="t")
    )
    completed = complete_trial(trial_repo, trial, verdict="fail")
    assert completed.status == "failed"
    assert completed.verdict == "fail"


def test_build_summary_counts_stage_statuses():
    trial_repo = InMemoryProjectBuildTrialRepository()
    stage_repo = InMemoryProjectBuildTrialStageRepository()
    trial = create_trial(
        trial_repo, project_id="p1", body=ProjectBuildTrialCreate(name="t")
    )
    for status in ("passed", "passed", "failed", "skipped"):
        add_stage(
            stage_repo,
            project_id="p1",
            trial_id=trial.id,
            body=ProjectBuildTrialStageCreate(
                name=status,
                stage_type="setup",
                status=status,  # type: ignore[arg-type]
            ),
        )
    summary = build_summary(trial, stage_repo.list_by_trial(trial.id))
    assert summary.total_stages == 4
    assert summary.stage_counts["passed"] == 2
    assert summary.stage_counts["failed"] == 1
    assert summary.stage_counts["skipped"] == 1
    assert summary.stage_counts["pending"] == 0


# -- API tests --------------------------------------------------------------


def test_create_trial_unknown_project_returns_404(client):
    res = client.post(
        "/projects/missing/build-trials", json={"name": "t"}
    )
    assert res.status_code == 404


def test_full_trial_lifecycle_via_api(client, project):
    project_id = project["id"]
    created = client.post(
        f"/projects/{project_id}/build-trials",
        json={"name": "real-build", "goal": "build foo", "trial_type": "real_project"},
    )
    assert created.status_code == 201
    trial = created.json()

    listed = client.get(f"/projects/{project_id}/build-trials").json()
    assert len(listed) == 1

    # Add stages
    stage_res = client.post(
        f"/build-trials/{trial['id']}/stages",
        json={"name": "setup", "stage_type": "setup", "status": "passed"},
    )
    assert stage_res.status_code == 201
    client.post(
        f"/build-trials/{trial['id']}/stages",
        json={"name": "tests", "stage_type": "check", "status": "failed"},
    )

    stages = client.get(f"/build-trials/{trial['id']}/stages").json()
    assert len(stages) == 2

    # Update stage
    stage_id = stages[0]["id"]
    updated_stage = client.patch(
        f"/build-trial-stages/{stage_id}",
        json={"notes": "looks good", "status": "passed"},
    ).json()
    assert updated_stage["notes"] == "looks good"

    # Update trial
    updated_trial = client.patch(
        f"/build-trials/{trial['id']}",
        json={"status": "running"},
    ).json()
    assert updated_trial["status"] == "running"
    assert updated_trial["started_at"] is not None

    # Summary endpoint
    summary = client.get(f"/build-trials/{trial['id']}").json()
    assert summary["total_stages"] == 2
    assert summary["stage_counts"]["passed"] == 1
    assert summary["stage_counts"]["failed"] == 1

    # Complete
    completed = client.post(
        f"/build-trials/{trial['id']}/complete",
        json={"verdict": "pass_with_manual_fallback", "summary": "ok"},
    ).json()
    assert completed["verdict"] == "pass_with_manual_fallback"
    assert completed["status"] == "completed"


def test_get_trial_missing_returns_404(client):
    res = client.get("/build-trials/missing")
    assert res.status_code == 404


def test_add_stage_to_missing_trial_returns_404(client):
    res = client.post(
        "/build-trials/missing/stages",
        json={"name": "x", "stage_type": "setup"},
    )
    assert res.status_code == 404
