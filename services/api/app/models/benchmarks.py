from datetime import datetime
from typing import Literal

from pydantic import BaseModel

BenchmarkScenarioType = Literal[
    "requirement_analysis",
    "task_decomposition",
    "check_execution",
    "pr_review",
    "incident_analysis",
    "memory_learning",
    "end_to_end_trial",
    "custom",
]

BenchmarkRunStatus = Literal[
    "pending", "running", "completed", "failed", "skipped"
]

BenchmarkRunResultStatus = Literal[
    "pending", "passed", "failed", "skipped", "inconclusive"
]


class BenchmarkScenarioCreate(BaseModel):
    name: str
    description: str = ""
    scenario_type: BenchmarkScenarioType = "custom"
    project_id: str | None = None
    input_payload: dict = {}
    expected_outcomes: dict = {}
    enabled: bool = True
    tags: list[str] = []


class BenchmarkScenarioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scenario_type: BenchmarkScenarioType | None = None
    input_payload: dict | None = None
    expected_outcomes: dict | None = None
    enabled: bool | None = None
    tags: list[str] | None = None


class BenchmarkScenario(BaseModel):
    id: str
    project_id: str | None = None
    name: str
    description: str = ""
    scenario_type: BenchmarkScenarioType = "custom"
    input_payload: dict = {}
    expected_outcomes: dict = {}
    enabled: bool = True
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime


class BenchmarkRunCreate(BaseModel):
    provider: str | None = None
    model: str | None = None
    summary: str | None = None


class BenchmarkRunUpdate(BaseModel):
    status: BenchmarkRunStatus | None = None
    summary: str | None = None
    error_message: str | None = None


class BenchmarkRun(BaseModel):
    id: str
    project_id: str | None = None
    scenario_id: str
    status: BenchmarkRunStatus = "pending"
    provider: str | None = None
    model: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BenchmarkRunResultCreate(BaseModel):
    status: BenchmarkRunResultStatus = "pending"
    score: float | None = None
    passed: bool = False
    observations: str = ""
    metrics: dict = {}
    artifact_id: str | None = None


class BenchmarkRunResult(BaseModel):
    id: str
    benchmark_run_id: str
    scenario_id: str
    status: BenchmarkRunResultStatus = "pending"
    score: float | None = None
    passed: bool = False
    observations: str = ""
    metrics: dict = {}
    artifact_id: str | None = None
    created_at: datetime
    updated_at: datetime
