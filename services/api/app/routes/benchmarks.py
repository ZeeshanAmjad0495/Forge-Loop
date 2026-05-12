from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_auth
from ..models import (
    BenchmarkRun,
    BenchmarkRunCreate,
    BenchmarkRunResult,
    BenchmarkRunResultCreate,
    BenchmarkScenario,
    BenchmarkScenarioCreate,
    BenchmarkScenarioUpdate,
)
from ..repositories_state import (
    benchmark_run_repo,
    benchmark_run_result_repo,
    benchmark_scenario_repo,
    project_repo,
)
from ..services.regression_benchmarks import (
    create_run,
    create_scenario,
    record_result,
    update_scenario,
)

router = APIRouter()


@router.post(
    "/benchmark-scenarios",
    response_model=BenchmarkScenario,
    status_code=201,
)
def create_benchmark_scenario(
    body: BenchmarkScenarioCreate,
    current_user: str = Depends(require_auth),
):
    if body.project_id is not None and project_repo.get(body.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return create_scenario(benchmark_scenario_repo, body)


@router.get(
    "/benchmark-scenarios",
    response_model=list[BenchmarkScenario],
)
def list_benchmark_scenarios(
    project_id: str | None = Query(default=None),
    current_user: str = Depends(require_auth),
):
    if project_id is not None:
        return benchmark_scenario_repo.list_by_project(project_id)
    return benchmark_scenario_repo.list_all()


@router.get(
    "/benchmark-scenarios/{scenario_id}",
    response_model=BenchmarkScenario,
)
def get_benchmark_scenario(
    scenario_id: str,
    current_user: str = Depends(require_auth),
):
    scenario = benchmark_scenario_repo.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Benchmark scenario not found")
    return scenario


@router.patch(
    "/benchmark-scenarios/{scenario_id}",
    response_model=BenchmarkScenario,
)
def patch_benchmark_scenario(
    scenario_id: str,
    body: BenchmarkScenarioUpdate,
    current_user: str = Depends(require_auth),
):
    scenario = benchmark_scenario_repo.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Benchmark scenario not found")
    return update_scenario(benchmark_scenario_repo, scenario, body)


@router.post(
    "/benchmark-scenarios/{scenario_id}/runs",
    response_model=BenchmarkRun,
    status_code=201,
)
def create_benchmark_run(
    scenario_id: str,
    body: BenchmarkRunCreate,
    current_user: str = Depends(require_auth),
):
    scenario = benchmark_scenario_repo.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Benchmark scenario not found")
    return create_run(benchmark_run_repo, scenario, body)


@router.get(
    "/benchmark-scenarios/{scenario_id}/runs",
    response_model=list[BenchmarkRun],
)
def list_benchmark_runs(
    scenario_id: str,
    current_user: str = Depends(require_auth),
):
    if benchmark_scenario_repo.get(scenario_id) is None:
        raise HTTPException(status_code=404, detail="Benchmark scenario not found")
    return benchmark_run_repo.list_by_scenario(scenario_id)


@router.get("/benchmark-runs/{run_id}", response_model=BenchmarkRun)
def get_benchmark_run(
    run_id: str,
    current_user: str = Depends(require_auth),
):
    run = benchmark_run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return run


@router.post(
    "/benchmark-runs/{run_id}/results",
    response_model=BenchmarkRunResult,
    status_code=201,
)
def add_benchmark_run_result(
    run_id: str,
    body: BenchmarkRunResultCreate,
    current_user: str = Depends(require_auth),
):
    run = benchmark_run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return record_result(benchmark_run_result_repo, run, body)


@router.get(
    "/benchmark-runs/{run_id}/results",
    response_model=list[BenchmarkRunResult],
)
def list_benchmark_run_results(
    run_id: str,
    current_user: str = Depends(require_auth),
):
    if benchmark_run_repo.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return benchmark_run_result_repo.list_by_run(run_id)
