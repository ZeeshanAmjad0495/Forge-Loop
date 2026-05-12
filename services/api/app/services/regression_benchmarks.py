"""Regression benchmark suite (Release 10, Task 62).

Lightweight scaffolding for repeatable benchmark scenarios and recorded
results. No real LLM execution — callers (humans or future evaluator agents)
post results through the API. The service tracks scenario/run/result state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    BenchmarkRun,
    BenchmarkRunCreate,
    BenchmarkRunResult,
    BenchmarkRunResultCreate,
    BenchmarkRunUpdate,
    BenchmarkScenario,
    BenchmarkScenarioCreate,
    BenchmarkScenarioUpdate,
)
from ..repositories import (
    BenchmarkRunRepository,
    BenchmarkRunResultRepository,
    BenchmarkScenarioRepository,
)


def create_scenario(
    repo: BenchmarkScenarioRepository, body: BenchmarkScenarioCreate
) -> BenchmarkScenario:
    now = datetime.now(timezone.utc)
    scenario = BenchmarkScenario(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        scenario_type=body.scenario_type,
        input_payload=dict(body.input_payload),
        expected_outcomes=dict(body.expected_outcomes),
        enabled=body.enabled,
        tags=list(body.tags),
        created_at=now,
        updated_at=now,
    )
    repo.save(scenario)
    return scenario


def update_scenario(
    repo: BenchmarkScenarioRepository,
    scenario: BenchmarkScenario,
    body: BenchmarkScenarioUpdate,
) -> BenchmarkScenario:
    data = scenario.model_dump()
    for field, value in body.model_dump(exclude_unset=True).items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = BenchmarkScenario(**data)
    repo.update(updated)
    return updated


def create_run(
    repo: BenchmarkRunRepository,
    scenario: BenchmarkScenario,
    body: BenchmarkRunCreate,
) -> BenchmarkRun:
    now = datetime.now(timezone.utc)
    run = BenchmarkRun(
        id=str(uuid.uuid4()),
        project_id=scenario.project_id,
        scenario_id=scenario.id,
        provider=body.provider,
        model=body.model,
        summary=body.summary,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    repo.save(run)
    return run


def update_run(
    repo: BenchmarkRunRepository,
    run: BenchmarkRun,
    body: BenchmarkRunUpdate,
) -> BenchmarkRun:
    data = run.model_dump()
    now = datetime.now(timezone.utc)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    new_status = data.get("status")
    if new_status == "running" and run.status != "running" and not data.get("started_at"):
        data["started_at"] = now
    if (
        new_status in {"completed", "failed", "skipped"}
        and not data.get("completed_at")
    ):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = BenchmarkRun(**data)
    repo.update(updated)
    return updated


def record_result(
    repo: BenchmarkRunResultRepository,
    run: BenchmarkRun,
    body: BenchmarkRunResultCreate,
) -> BenchmarkRunResult:
    now = datetime.now(timezone.utc)
    result = BenchmarkRunResult(
        id=str(uuid.uuid4()),
        benchmark_run_id=run.id,
        scenario_id=run.scenario_id,
        status=body.status,
        score=body.score,
        passed=body.passed,
        observations=body.observations,
        metrics=dict(body.metrics),
        artifact_id=body.artifact_id,
        created_at=now,
        updated_at=now,
    )
    repo.save(result)
    return result
