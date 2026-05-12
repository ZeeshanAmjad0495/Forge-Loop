import pytest

from app.models import (
    ExperimentPlanCreate,
    ExperimentPlanUpdate,
    ExperimentRunComplete,
    ExperimentRunCreate,
    ExperimentRunUpdate,
)
from app.repositories import (
    InMemoryExperimentPlanRepository,
    InMemoryExperimentRunRepository,
)
from app.services.experiments import (
    InvalidExperimentTransition,
    approve_plan,
    complete_run,
    create_plan,
    create_run,
    reject_plan,
    update_plan,
    update_run,
)


# -- service unit tests ---------------------------------------------------


def test_create_plan_defaults():
    repo = InMemoryExperimentPlanRepository()
    plan = create_plan(
        repo,
        body=ExperimentPlanCreate(
            title="Compare DeepSeek vs Kimi",
            hypothesis="Kimi is better for long-context tasks.",
            metric_names=["accuracy", "latency_ms"],
        ),
    )
    assert plan.status == "proposed"
    assert plan.metric_names == ["accuracy", "latency_ms"]


def test_approve_then_running_then_complete():
    plan_repo = InMemoryExperimentPlanRepository()
    run_repo = InMemoryExperimentRunRepository()
    plan = create_plan(plan_repo, body=ExperimentPlanCreate(title="t"))
    approved = approve_plan(plan_repo, plan)
    assert approved.status == "approved"
    assert approved.approved_at is not None

    run = create_run(
        run_repo,
        plan=approved,
        body=ExperimentRunCreate(
            status="running",
            baseline_metrics={"accuracy": 0.7},
        ),
    )
    assert run.status == "running"
    assert run.started_at is not None

    completed = complete_run(
        run_repo,
        run,
        ExperimentRunComplete(
            decision="accept_change",
            result_metrics={"accuracy": 0.85},
            summary="moved metrics up",
        ),
    )
    assert completed.status == "completed"
    assert completed.decision == "accept_change"
    assert completed.result_metrics == {"accuracy": 0.85}
    assert completed.completed_at is not None


def test_reject_plan_blocks_running():
    repo = InMemoryExperimentPlanRepository()
    plan = create_plan(repo, body=ExperimentPlanCreate(title="t"))
    rejected = reject_plan(repo, plan)
    assert rejected.status == "rejected"
    # rejected cannot go straight to running
    with pytest.raises(InvalidExperimentTransition):
        from app.services.experiments import _transition_plan

        _transition_plan(repo, rejected, "running")


def test_update_run_running_sets_started_at():
    plan_repo = InMemoryExperimentPlanRepository()
    run_repo = InMemoryExperimentRunRepository()
    plan = create_plan(plan_repo, body=ExperimentPlanCreate(title="t"))
    run = create_run(run_repo, plan=plan, body=ExperimentRunCreate())
    assert run.started_at is None
    updated = update_run(run_repo, run, ExperimentRunUpdate(status="running"))
    assert updated.status == "running"
    assert updated.started_at is not None


def test_update_plan_modifies_fields():
    repo = InMemoryExperimentPlanRepository()
    plan = create_plan(repo, body=ExperimentPlanCreate(title="t"))
    updated = update_plan(
        repo,
        plan,
        ExperimentPlanUpdate(
            hypothesis="new hypothesis",
            metric_names=["m1", "m2"],
            success_criteria="m1 > 0.8",
        ),
    )
    assert updated.hypothesis == "new hypothesis"
    assert updated.metric_names == ["m1", "m2"]


# -- API tests ------------------------------------------------------------


def test_create_experiment_plan_via_api(client):
    res = client.post(
        "/experiment-plans",
        json={"title": "Test plan", "metric_names": ["pass_rate"]},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "proposed"


def test_experiment_plan_with_unknown_proposal_id_rejected(client):
    res = client.post(
        "/experiment-plans",
        json={"title": "t", "proposal_id": "missing"},
    )
    assert res.status_code == 400


def test_experiment_plan_link_to_real_proposal(client):
    proposal = client.post(
        "/improvement-proposals", json={"title": "p"}
    ).json()
    res = client.post(
        "/experiment-plans",
        json={"title": "linked", "proposal_id": proposal["id"]},
    )
    assert res.status_code == 201
    listed = client.get(
        f"/experiment-plans?proposal_id={proposal['id']}"
    ).json()
    assert len(listed) == 1


def test_approve_and_create_run_via_api(client):
    plan = client.post(
        "/experiment-plans",
        json={"title": "t", "metric_names": ["accuracy"]},
    ).json()
    approved = client.post(
        f"/experiment-plans/{plan['id']}/approve"
    ).json()
    assert approved["status"] == "approved"

    run = client.post(
        f"/experiment-plans/{plan['id']}/runs",
        json={"baseline_metrics": {"accuracy": 0.7}},
    ).json()
    assert run["status"] == "pending"
    assert run["baseline_metrics"] == {"accuracy": 0.7}

    listed = client.get(f"/experiment-plans/{plan['id']}/runs").json()
    assert len(listed) == 1


def test_complete_run_records_decision(client):
    plan = client.post("/experiment-plans", json={"title": "t"}).json()
    client.post(f"/experiment-plans/{plan['id']}/approve")
    run = client.post(
        f"/experiment-plans/{plan['id']}/runs",
        json={"status": "running"},
    ).json()

    completed = client.post(
        f"/experiment-runs/{run['id']}/complete",
        json={
            "decision": "accept_change",
            "result_metrics": {"accuracy": 0.85},
            "summary": "ok",
        },
    ).json()
    assert completed["status"] == "completed"
    assert completed["decision"] == "accept_change"
    assert completed["result_metrics"] == {"accuracy": 0.85}


def test_reject_plan_returns_409_on_running(client):
    plan = client.post("/experiment-plans", json={"title": "t"}).json()
    client.post(f"/experiment-plans/{plan['id']}/reject")
    # rejected -> running is invalid
    res = client.post(f"/experiment-plans/{plan['id']}/approve")
    # rejected -> approved is also invalid
    assert res.status_code == 409


def test_patch_run_updates_metrics(client):
    plan = client.post("/experiment-plans", json={"title": "t"}).json()
    run = client.post(
        f"/experiment-plans/{plan['id']}/runs",
        json={},
    ).json()
    patched = client.patch(
        f"/experiment-runs/{run['id']}",
        json={"result_metrics": {"latency_ms": 120}},
    ).json()
    assert patched["result_metrics"] == {"latency_ms": 120}
