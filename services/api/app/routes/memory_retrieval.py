from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..repositories_state import memory_candidate_repo, project_repo
from ..services.memory_retrieval import (
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    retrieve_memory,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/memory/retrieve",
    response_model=MemoryRetrievalResponse,
)
def retrieve_project_memory(
    project_id: str,
    body: MemoryRetrievalRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return retrieve_memory(memory_candidate_repo, project_id, body)
