"""Task 92: DB-backed local background jobs.

Moves long-running work off the request/response path. A Job is the
durable source of truth (stored via the repository abstraction — never
the ephemeral Task-80 WorkflowEngine). The worker drains queued jobs
explicitly (no daemon); Temporal/NATS/distributed workers are out of
scope (Tasks 93/94).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
# One safe job type wired in Task 92 (deterministic, no external calls).
JobType = Literal["artifact_summary"]


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict = {}
    max_attempts: int | None = None
    timeout_seconds: int | None = None


class Job(BaseModel):
    id: str
    project_id: str
    job_type: JobType
    status: JobStatus = "queued"
    payload: dict = {}
    result: dict | None = None
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: int = 300
    failure_reason: str | None = None
    heartbeat_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobAttempt(BaseModel):
    id: str
    job_id: str
    project_id: str
    attempt_no: int
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
