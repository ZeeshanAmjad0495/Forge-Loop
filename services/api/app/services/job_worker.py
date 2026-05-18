"""Task 92: DB-backed local background worker.

Moves long-running work off the request/response path. The Job
repository is the durable source of truth (NOT the ephemeral Task-80
WorkflowEngine). The worker drains queued jobs *explicitly* via
``run_once`` — there is no daemon thread (deterministic, single-worker;
Temporal/NATS/distributed workers are out of scope, Tasks 93/94).

One safe job type is wired: ``artifact_summary`` (deterministic
``summarize_artifact`` — never calls a real LLM, no external effects).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .. import config
from ..models import Job, JobAttempt, JobCreate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(
    job_repo, *, project_id: str, body: JobCreate
) -> Job:
    now = _now()
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        job_type=body.job_type,
        status="queued",
        payload=dict(body.payload or {}),
        max_attempts=int(
            body.max_attempts or config.JOB_DEFAULT_MAX_ATTEMPTS
        ),
        timeout_seconds=int(
            body.timeout_seconds or config.JOB_DEFAULT_TIMEOUT_SECONDS
        ),
        created_at=now,
        updated_at=now,
    )
    job_repo.save(job)
    return job


def _handle_artifact_summary(job: Job) -> dict:
    """Deterministic, no external calls."""
    from ..repositories_state import artifact_repo, artifact_summary_repo
    from .artifact_summaries import summarize_artifact

    artifact_id = (job.payload or {}).get("artifact_id")
    if not artifact_id:
        raise ValueError("payload.artifact_id is required")
    artifact = artifact_repo.get(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact {artifact_id!r} not found")
    summary = summarize_artifact(
        artifact_summary_repo,
        artifact,
        summary_type=(job.payload or {}).get("summary_type", "short"),
        project_id=job.project_id,
    )
    return {"artifact_summary_id": summary.id, "status": summary.status}


_JOB_HANDLERS = {
    "artifact_summary": _handle_artifact_summary,
}


def _run_job(job_repo, job_attempt_repo, job: Job) -> Job:
    now = _now()
    job.status = "running"
    job.attempts += 1
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.updated_at = now
    job_repo.update(job)

    attempt = JobAttempt(
        id=str(uuid.uuid4()),
        job_id=job.id,
        project_id=job.project_id,
        attempt_no=job.attempts,
        status="running",
        started_at=now,
    )
    job_attempt_repo.save(attempt)

    handler = _JOB_HANDLERS.get(job.job_type)
    try:
        if handler is None:
            raise ValueError(f"no handler for job_type {job.job_type!r}")
        result = handler(job)
        end = _now()
        job.status = "succeeded"
        job.result = result
        job.failure_reason = None
        job.finished_at = end
        job.updated_at = end
        attempt.status = "succeeded"
        attempt.finished_at = end
    except Exception as exc:  # noqa: BLE001 — recorded as failure_reason
        end = _now()
        reason = f"{type(exc).__name__}: {exc}"
        attempt.status = "failed"
        attempt.finished_at = end
        attempt.error = reason
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.finished_at = end
        else:
            job.status = "queued"  # eligible for retry on the next drain
        job.failure_reason = reason
        job.updated_at = end
    finally:
        job_attempt_repo.save(attempt)
        job_repo.update(job)
    return job


def run_once(job_repo, job_attempt_repo, *, max_jobs: int = 10) -> list[Job]:
    """Explicitly drain up to ``max_jobs`` queued jobs. Opt-in: a no-op
    unless ``BACKGROUND_WORKER_ENABLED``. No daemon, no thread — the
    caller decides when to drain (deterministic, single-worker)."""
    if not config.BACKGROUND_WORKER_ENABLED:
        return []
    drained: list[Job] = []
    for _ in range(max(1, int(max_jobs))):
        queued = job_repo.list_queued()
        # Skip jobs that already exhausted their attempts (defensive).
        queued = [j for j in queued if j.attempts < j.max_attempts]
        if not queued:
            break
        job = _run_job(job_repo, job_attempt_repo, queued[0])
        drained.append(job)
    return drained
