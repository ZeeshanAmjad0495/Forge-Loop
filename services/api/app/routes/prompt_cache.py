from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import PromptContextCacheEntry
from ..repositories_state import project_repo, prompt_cache_repo

router = APIRouter()


@router.get(
    "/projects/{project_id}/prompt-context-cache",
    response_model=list[PromptContextCacheEntry],
)
def list_cache_entries(
    project_id: str,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return prompt_cache_repo.list_by_project(project_id)


@router.get(
    "/prompt-context-cache/{cache_entry_id}",
    response_model=PromptContextCacheEntry,
)
def get_cache_entry(
    cache_entry_id: str,
    current_user: str = Depends(require_auth),
):
    entry = prompt_cache_repo.get(cache_entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return entry


@router.delete(
    "/prompt-context-cache/{cache_entry_id}",
    status_code=204,
)
def delete_cache_entry(
    cache_entry_id: str,
    current_user: str = Depends(require_auth),
):
    if prompt_cache_repo.get(cache_entry_id) is None:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    prompt_cache_repo.delete(cache_entry_id)
    return None
