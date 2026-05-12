import pytest

from app.repositories import InMemoryCostRecordRepository
from app.services.cost_tracking import record_cost


# -- model / service unit tests --------------------------------------------


def test_record_cost_computes_totals():
    repo = InMemoryCostRecordRepository()
    record = record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="run-1",
        workflow_type="analysis",
        provider="mock",
        model="mock-1",
        input_tokens=100,
        output_tokens=50,
        cached_input_tokens=10,
        estimated_input_cost_usd=0.01,
        estimated_output_cost_usd=0.02,
        estimated_cached_input_cost_usd=0.001,
    )
    assert record.total_tokens == 160
    assert record.estimated_total_cost_usd == pytest.approx(0.031)
    assert record.currency == "USD"
    assert repo.get(record.id) == record


def test_record_cost_zero_values_for_mock():
    repo = InMemoryCostRecordRepository()
    record = record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="run-2",
        workflow_type="analysis",
        provider="mock",
        model="mock-1",
    )
    assert record.input_tokens == 0
    assert record.total_tokens == 0
    assert record.estimated_total_cost_usd == 0.0


def test_record_cost_clamps_negative_inputs():
    repo = InMemoryCostRecordRepository()
    record = record_cost(
        repo,
        project_id="p1",
        source_type="manual",
        source_id="m-1",
        workflow_type="manual",
        provider="mock",
        model="mock-1",
        input_tokens=-5,
        estimated_input_cost_usd=-1.0,
    )
    assert record.input_tokens == 0
    assert record.estimated_input_cost_usd == 0.0


def test_repo_list_by_project_and_source():
    repo = InMemoryCostRecordRepository()
    record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="a",
        workflow_type="analysis",
        provider="mock",
        model="m",
    )
    record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="b",
        workflow_type="analysis",
        provider="mock",
        model="m",
    )
    record_cost(
        repo,
        project_id="p2",
        source_type="agent_run",
        source_id="a",
        workflow_type="analysis",
        provider="mock",
        model="m",
    )
    assert len(repo.list_by_project("p1")) == 2
    assert len(repo.list_by_project("p2")) == 1
    by_source = repo.list_by_source("agent_run", "a")
    assert len(by_source) == 2


def test_repo_list_by_provider_model_and_workflow():
    repo = InMemoryCostRecordRepository()
    record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="a",
        workflow_type="analysis",
        provider="mock",
        model="m1",
    )
    record_cost(
        repo,
        project_id="p1",
        source_type="agent_run",
        source_id="b",
        workflow_type="coding",
        provider="deepseek",
        model="d1",
    )
    only_mock = repo.list_by_provider_model("p1", provider="mock")
    assert len(only_mock) == 1
    only_d1 = repo.list_by_provider_model("p1", model="d1")
    assert len(only_d1) == 1
    coding = repo.list_by_workflow("p1", "coding")
    assert len(coding) == 1


# -- API tests --------------------------------------------------------------


def test_list_cost_records_for_unknown_project_returns_404(client):
    res = client.get("/projects/missing/cost-records")
    assert res.status_code == 404


def test_create_and_list_cost_records(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/cost-records",
        json={
            "source_type": "agent_run",
            "source_id": "run-1",
            "workflow_type": "analysis",
            "provider": "mock",
            "model": "mock-1",
            "input_tokens": 10,
            "output_tokens": 5,
        },
    )
    assert res.status_code == 201
    created = res.json()
    assert created["project_id"] == project_id
    assert created["total_tokens"] == 15

    list_res = client.get(f"/projects/{project_id}/cost-records")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


def test_get_cost_record_by_id(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/cost-records",
        json={
            "source_type": "manual",
            "source_id": "x",
            "workflow_type": "manual",
            "provider": "mock",
            "model": "mock-1",
        },
    )
    record_id = res.json()["id"]
    got = client.get(f"/cost-records/{record_id}")
    assert got.status_code == 200
    assert got.json()["id"] == record_id


def test_get_cost_record_missing_returns_404(client):
    res = client.get("/cost-records/does-not-exist")
    assert res.status_code == 404


def test_list_cost_records_filters_by_workflow(client, project):
    project_id = project["id"]
    for wf in ("analysis", "coding", "analysis"):
        client.post(
            f"/projects/{project_id}/cost-records",
            json={
                "source_type": "agent_run",
                "source_id": "s",
                "workflow_type": wf,
                "provider": "mock",
                "model": "m",
            },
        )
    res = client.get(
        f"/projects/{project_id}/cost-records", params={"workflow_type": "analysis"}
    )
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_cost_records_filters_by_provider_and_model(client, project):
    project_id = project["id"]
    client.post(
        f"/projects/{project_id}/cost-records",
        json={
            "source_type": "agent_run",
            "source_id": "s",
            "workflow_type": "analysis",
            "provider": "mock",
            "model": "m1",
        },
    )
    client.post(
        f"/projects/{project_id}/cost-records",
        json={
            "source_type": "agent_run",
            "source_id": "s",
            "workflow_type": "analysis",
            "provider": "deepseek",
            "model": "d1",
        },
    )
    res = client.get(
        f"/projects/{project_id}/cost-records", params={"provider": "deepseek"}
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["provider"] == "deepseek"
