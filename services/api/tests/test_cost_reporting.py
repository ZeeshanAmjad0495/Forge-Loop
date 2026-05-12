from app.models import ProjectBuildTrialCreate
from app.repositories_state import (
    cost_record_repo,
    project_build_trial_repo,
)
from app.services.cost_tracking import record_cost
from app.services.evaluation_trials import create_trial


def test_empty_project_cost_report(client, project):
    res = client.get(f"/projects/{project['id']}/cost-report")
    assert res.status_code == 200
    body = res.json()
    assert body["total_estimated_cost_usd"] == 0.0
    assert body["record_count"] == 0


def test_unknown_project_cost_report(client):
    res = client.get("/projects/missing/cost-report")
    assert res.status_code == 404


def test_project_cost_report_groups_by_provider_and_workflow(client, project):
    project_id = project["id"]
    record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type="agent_run",
        source_id="run-1",
        workflow_type="analysis",
        provider="deepseek",
        model="d1",
        estimated_input_cost_usd=0.5,
    )
    record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type="agent_run",
        source_id="run-2",
        workflow_type="coding",
        provider="kimi",
        model="k1",
        estimated_input_cost_usd=1.5,
    )
    body = client.get(f"/projects/{project_id}/cost-report").json()
    assert body["total_estimated_cost_usd"] == 2.0
    assert body["record_count"] == 2
    assert body["by_provider"]["deepseek"] == 0.5
    assert body["by_provider"]["kimi"] == 1.5
    assert body["by_workflow_type"]["coding"] == 1.5


def test_trial_cost_report_filters_by_source(client, project):
    project_id = project["id"]
    trial = create_trial(
        project_build_trial_repo,
        project_id=project_id,
        body=ProjectBuildTrialCreate(name="t"),
    )
    record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type="build_trial",
        source_id=trial.id,
        workflow_type="analysis",
        provider="deepseek",
        model="d1",
        estimated_input_cost_usd=2.0,
    )
    record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type="agent_run",
        source_id="run",
        workflow_type="analysis",
        provider="deepseek",
        model="d1",
        estimated_input_cost_usd=10.0,
    )
    body = client.get(f"/build-trials/{trial.id}/cost-report").json()
    assert body["total_estimated_cost_usd"] == 2.0
    assert body["record_count"] == 1


def test_trial_cost_report_notes_when_empty(client, project):
    project_id = project["id"]
    trial = create_trial(
        project_build_trial_repo,
        project_id=project_id,
        body=ProjectBuildTrialCreate(name="t"),
    )
    body = client.get(f"/build-trials/{trial.id}/cost-report").json()
    assert body["record_count"] == 0
    assert body["notes"]


def test_trial_cost_report_unknown(client):
    res = client.get("/build-trials/missing/cost-report")
    assert res.status_code == 404


def test_dev_task_and_requirement_unknown(client):
    assert client.get("/dev-tasks/missing/cost-report").status_code == 404
    assert client.get("/requirements/missing/cost-report").status_code == 404
