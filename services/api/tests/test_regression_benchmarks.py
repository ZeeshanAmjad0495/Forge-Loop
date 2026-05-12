def _create_scenario(client, **kwargs):
    body = {
        "name": "deepseek-regression",
        "description": "checks deepseek regression",
        "scenario_type": "requirement_analysis",
        "input_payload": {"prompt": "hi"},
        "expected_outcomes": {"keywords": ["plan"]},
        "tags": ["smoke"],
    }
    body.update(kwargs)
    return client.post("/benchmark-scenarios", json=body)


def test_create_and_list_scenario(client):
    res = _create_scenario(client)
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "deepseek-regression"

    listed = client.get("/benchmark-scenarios").json()
    assert len(listed) == 1


def test_list_scenarios_filtered_by_project(client, project):
    project_id = project["id"]
    _create_scenario(client, project_id=project_id, name="for-project")
    _create_scenario(client, name="global")
    listed = client.get(
        "/benchmark-scenarios", params={"project_id": project_id}
    ).json()
    assert len(listed) == 1
    assert listed[0]["name"] == "for-project"


def test_get_scenario_missing_returns_404(client):
    res = client.get("/benchmark-scenarios/missing")
    assert res.status_code == 404


def test_create_scenario_unknown_project_returns_404(client):
    res = _create_scenario(client, project_id="missing")
    assert res.status_code == 404


def test_update_scenario(client):
    scenario = _create_scenario(client).json()
    res = client.patch(
        f"/benchmark-scenarios/{scenario['id']}",
        json={"enabled": False, "tags": ["regression"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False
    assert body["tags"] == ["regression"]


def test_create_run_and_record_results(client):
    scenario = _create_scenario(client).json()
    run = client.post(
        f"/benchmark-scenarios/{scenario['id']}/runs",
        json={"provider": "mock", "model": "mock-1"},
    )
    assert run.status_code == 201
    run_body = run.json()
    assert run_body["status"] == "pending"
    assert run_body["scenario_id"] == scenario["id"]

    runs = client.get(f"/benchmark-scenarios/{scenario['id']}/runs").json()
    assert len(runs) == 1

    fetched_run = client.get(f"/benchmark-runs/{run_body['id']}").json()
    assert fetched_run["id"] == run_body["id"]

    result = client.post(
        f"/benchmark-runs/{run_body['id']}/results",
        json={
            "status": "passed",
            "passed": True,
            "score": 0.9,
            "observations": "ok",
            "metrics": {"latency_ms": 120},
        },
    )
    assert result.status_code == 201
    rbody = result.json()
    assert rbody["passed"] is True
    assert rbody["score"] == 0.9
    assert rbody["scenario_id"] == scenario["id"]

    results = client.get(f"/benchmark-runs/{run_body['id']}/results").json()
    assert len(results) == 1


def test_run_endpoints_404_when_missing(client):
    assert (
        client.post("/benchmark-scenarios/missing/runs", json={}).status_code == 404
    )
    assert client.get("/benchmark-runs/missing").status_code == 404
    assert (
        client.post("/benchmark-runs/missing/results", json={}).status_code == 404
    )
    assert client.get("/benchmark-runs/missing/results").status_code == 404


def test_list_runs_missing_scenario(client):
    assert (
        client.get("/benchmark-scenarios/missing/runs").status_code == 404
    )
