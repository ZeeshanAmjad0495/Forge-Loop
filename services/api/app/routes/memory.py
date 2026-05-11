from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    MemoryCandidateRejectRequest,
    MemoryLearningRun,
    MemoryLearningRunCreate,
    ProjectMemoryCandidate,
    ProjectMemoryCandidateCreate,
    ProjectMemoryCandidateUpdate,
)
from ..repositories_state import (
    memory_candidate_repo,
    memory_learning_run_repo,
    project_repo,
)
from ..services import memory_learning_workflow

router = APIRouter()


@router.post(
    "/projects/{project_id}/memory-learning-runs",
    response_model=MemoryLearningRun,
    status_code=201,
)
def create_memory_learning_run(
    project_id: str,
    body: MemoryLearningRunCreate,
    current_user: str = Depends(require_auth),
):
    return memory_learning_workflow.create_run(project_id, body, current_user)


@router.get(
    "/projects/{project_id}/memory-learning-runs",
    response_model=list[MemoryLearningRun],
)
def list_project_memory_learning_runs(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return memory_learning_run_repo.list_by_project(project_id)


@router.get("/memory-learning-runs/{run_id}", response_model=MemoryLearningRun)
def get_memory_learning_run(run_id: str, _: str = Depends(require_auth)):
    run = memory_learning_run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="MemoryLearningRun not found")
    return run


@router.post(
    "/projects/{project_id}/memory-candidates",
    response_model=ProjectMemoryCandidate,
    status_code=201,
)
def create_manual_memory_candidate(
    project_id: str,
    body: ProjectMemoryCandidateCreate,
    current_user: str = Depends(require_auth),
):
    return memory_learning_workflow.create_manual_candidate(project_id, body, current_user)


@router.get(
    "/projects/{project_id}/memory-candidates",
    response_model=list[ProjectMemoryCandidate],
)
def list_project_memory_candidates(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return memory_candidate_repo.list_by_project(project_id)


@router.get(
    "/memory-candidates/{candidate_id}",
    response_model=ProjectMemoryCandidate,
)
def get_memory_candidate(candidate_id: str, _: str = Depends(require_auth)):
    candidate = memory_candidate_repo.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="MemoryCandidate not found")
    return candidate


@router.patch(
    "/memory-candidates/{candidate_id}",
    response_model=ProjectMemoryCandidate,
)
def update_memory_candidate(
    candidate_id: str,
    body: ProjectMemoryCandidateUpdate,
    _: str = Depends(require_auth),
):
    return memory_learning_workflow.update_candidate(candidate_id, body)


@router.post(
    "/memory-candidates/{candidate_id}/approve",
    response_model=ProjectMemoryCandidate,
)
def approve_memory_candidate(
    candidate_id: str,
    current_user: str = Depends(require_auth),
):
    return memory_learning_workflow.approve_candidate(candidate_id, current_user)


@router.post(
    "/memory-candidates/{candidate_id}/reject",
    response_model=ProjectMemoryCandidate,
)
def reject_memory_candidate(
    candidate_id: str,
    body: MemoryCandidateRejectRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    return memory_learning_workflow.reject_candidate(candidate_id, body, current_user)
