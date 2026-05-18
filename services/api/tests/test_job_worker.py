"""Task 92 — DB-backed local background worker.

Worker is opt-in (BACKGROUND_WORKER_ENABLED); drains explicitly via
run_once (no daemon). The Job repository is the durable source of truth.
One safe job type: artifact_summary (deterministic, no external calls).
"""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.models import Artifact, JobCreate
from app.repositories_state import (
    artifact_repo,
    job_attempt_repo,
    job_repo,
    repos,
)
from app.services import job_worker

client = TestClient(app)


def _reset():
    repos.reset_all()


def _project() -> str:
    res = client.post("/projects", json={"name": "JP", "description": "d"})
    assert res.status_code == 201
    return res.json()["id"]


def _artifact(content="alpha\nbeta") -> str:
    art = Artifact(
        id=str(uuid.uuid4()),
        artifact_type="tool_run_result",
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    artifact_repo.save(art)
    return art.id


def test_enqueue_then_disabled_worker_is_noop(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "BACKGROUND_WORKER_ENABLED", False)
    pid = _project()
    job = job_worker.enqueue_job(
        job_repo,
        project_id=pid,
        body=JobCreate(job_type="artifact_summary", payload={"artifact_id": "x"}),
    )
    assert job.status == "queued"
    drained = job_worker.run_once(job_repo, job_attempt_repo)
    assert drained == []
    assert job_repo.get(job.id).status == "queued"


def test_artifact_summary_job_succeeds(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "BACKGROUND_WORKER_ENABLED", True)
    pid = _project()
    aid = _artifact("hello\nworld")
    job = job_worker.enqueue_job(
        job_repo,
        project_id=pid,
        body=JobCreate(
            job_type="artifact_summary", payload={"artifact_id": aid}
        ),
    )
    drained = job_worker.run_once(job_repo, job_attempt_repo)
    assert len(drained) == 1
    done = job_repo.get(job.id)
    assert done.status == "succeeded"
    assert done.result and "artifact_summary_id" in done.result
    assert done.heartbeat_at is not None
    assert done.started_at is not None and done.finished_at is not None
    attempts = job_attempt_repo.list_by_job(job.id)
    assert len(attempts) == 1 and attempts[0].status == "succeeded"


def test_failing_job_retries_then_fails(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "BACKGROUND_WORKER_ENABLED", True)
    pid = _project()
    job = job_worker.enqueue_job(
        job_repo,
        project_id=pid,
        body=JobCreate(
            job_type="artifact_summary",
            payload={},  # missing artifact_id -> handler raises
            max_attempts=2,
        ),
    )
    # First drain: attempt 1 fails -> requeued.
    job_worker.run_once(job_repo, job_attempt_repo, max_jobs=1)
    mid = job_repo.get(job.id)
    assert mid.status == "queued"
    assert mid.attempts == 1
    assert mid.failure_reason is not None
    # Second drain: attempt 2 fails -> terminal failed.
    job_worker.run_once(job_repo, job_attempt_repo, max_jobs=1)
    final = job_repo.get(job.id)
    assert final.status == "failed"
    assert final.attempts == 2
    assert len(job_attempt_repo.list_by_job(job.id)) == 2


def test_routes_enqueue_get_and_runtime(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "BACKGROUND_WORKER_ENABLED", False)
    pid = _project()
    r404 = client.post(
        "/projects/nope/jobs",
        json={"job_type": "artifact_summary", "payload": {}},
    )
    assert r404.status_code == 404
    enq = client.post(
        f"/projects/{pid}/jobs",
        json={"job_type": "artifact_summary", "payload": {"artifact_id": "a"}},
    )
    assert enq.status_code == 201
    jid = enq.json()["id"]
    assert client.get(f"/jobs/{jid}").json()["status"] == "queued"
    assert len(client.get(f"/projects/{pid}/jobs").json()) == 1
    # Disabled worker -> run-once returns [].
    assert client.post("/jobs/worker/run-once").json() == []
    rt = client.get("/runtime/background-worker").json()
    assert rt["enabled"] is False
    assert rt["source_of_truth"] == "job_repository_db_not_workflow_engine"


def test_run_once_route_drains_when_enabled(monkeypatch):
    _reset()
    monkeypatch.setattr(config, "BACKGROUND_WORKER_ENABLED", True)
    pid = _project()
    aid = _artifact("x\ny\nz")
    client.post(
        f"/projects/{pid}/jobs",
        json={
            "job_type": "artifact_summary",
            "payload": {"artifact_id": aid},
        },
    )
    drained = client.post("/jobs/worker/run-once").json()
    assert len(drained) == 1
    assert drained[0]["status"] == "succeeded"
