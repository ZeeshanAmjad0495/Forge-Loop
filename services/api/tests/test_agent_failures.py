def _create(client, project_id: str, **kwargs):
    body = {
        "summary": "tests fail",
        "category": "failing_tests",
        "severity": "high",
        "source_type": "check_run",
        "source_id": "cr-1",
    }
    body.update(kwargs)
    return client.post(f"/projects/{project_id}/agent-failures", json=body)


def test_create_failure_unknown_project_returns_404(client):
    res = _create(client, "missing")
    assert res.status_code == 404


def test_create_list_get_failure(client, project):
    project_id = project["id"]
    res = _create(client, project_id)
    assert res.status_code == 201
    created = res.json()
    assert created["category"] == "failing_tests"

    listed = client.get(f"/projects/{project_id}/agent-failures").json()
    assert len(listed) == 1

    got = client.get(f"/agent-failures/{created['id']}").json()
    assert got["id"] == created["id"]


def test_get_missing_failure_returns_404(client):
    res = client.get("/agent-failures/missing")
    assert res.status_code == 404


def test_patch_failure(client, project):
    project_id = project["id"]
    created = _create(client, project_id).json()
    res = client.patch(
        f"/agent-failures/{created['id']}",
        json={"severity": "blocker", "status": "acknowledged"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["severity"] == "blocker"
    assert body["status"] == "acknowledged"


def test_resolve_failure_sets_resolved_at(client, project):
    project_id = project["id"]
    created = _create(client, project_id).json()
    res = client.post(
        f"/agent-failures/{created['id']}/resolve",
        json={"resolution_summary": "fixed by retry"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved"
    assert body["resolution_summary"] == "fixed by retry"
    assert body["resolved_at"] is not None


def test_summary_counts(client, project):
    project_id = project["id"]
    _create(client, project_id, category="failing_tests", severity="high")
    _create(client, project_id, category="failing_tests", severity="blocker")
    _create(client, project_id, category="timeout", severity="medium",
            source_type="command_run", source_id="cmd-1")
    res = client.get(f"/projects/{project_id}/agent-failures/summary").json()
    assert res["total"] == 3
    assert res["by_category"]["failing_tests"] == 2
    assert res["by_category"]["timeout"] == 1
    assert res["by_severity"]["high"] == 1
    assert res["by_severity"]["blocker"] == 1
    assert res["by_source_type"]["check_run"] == 2
    assert res["by_source_type"]["command_run"] == 1


def test_summary_unknown_project(client):
    res = client.get("/projects/missing/agent-failures/summary")
    assert res.status_code == 404
