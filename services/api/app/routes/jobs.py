from fastapi import APIRouter, Depends, HTTPException

from .. import config
from ..auth import require_auth
from ..models import Job, JobCreate
from ..repositories_state import job_attempt_repo, job_repo, project_repo
from ..services import job_worker

router = APIRouter()


@router.post(
    "/projects/{project_id}/jobs", response_model=Job, status_code=201
)
def enqueue_job(
    project_id: str,
    body: JobCreate,
    _: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return job_worker.enqueue_job(
        job_repo, project_id=project_id, body=body
    )


@router.get("/projects/{project_id}/jobs", response_model=list[Job])
def list_project_jobs(
    project_id: str,
    _: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return job_repo.list_by_project(project_id)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, _: str = Depends(require_auth)):
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/worker/run-once", response_model=list[Job])
def run_worker_once(_: str = Depends(require_auth)):
    """Explicitly drain queued jobs (no daemon). No-op (returns []) when
    BACKGROUND_WORKER_ENABLED is false."""
    return job_worker.run_once(
        job_repo,
        job_attempt_repo,
        max_jobs=config.JOB_WORKER_MAX_DRAIN,
    )


@router.get("/runtime/background-worker")
def background_worker_runtime(_: str = Depends(require_auth)):
    return {
        "enabled": config.BACKGROUND_WORKER_ENABLED,
        "default_max_attempts": config.JOB_DEFAULT_MAX_ATTEMPTS,
        "default_timeout_seconds": config.JOB_DEFAULT_TIMEOUT_SECONDS,
        "max_drain_per_call": config.JOB_WORKER_MAX_DRAIN,
        "job_types": ["artifact_summary"],
        "source_of_truth": "job_repository_db_not_workflow_engine",
    }
