from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_auth
from ..models import ContextPack, ContextPackCreate
from ..repositories_state import context_pack_repo, project_repo
from ..services.context_packs import create_context_pack

router = APIRouter()


@router.get(
    "/projects/{project_id}/context-packs",
    response_model=list[ContextPack],
)
def list_context_packs(
    project_id: str,
    source_type: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if source_type and source_id:
        return [
            p
            for p in context_pack_repo.list_by_source(source_type, source_id)
            if p.project_id == project_id
        ]
    if target_type and target_id:
        return [
            p
            for p in context_pack_repo.list_by_target(target_type, target_id)
            if p.project_id == project_id
        ]
    return context_pack_repo.list_by_project(project_id)


@router.get(
    "/context-packs/{context_pack_id}",
    response_model=ContextPack,
)
def get_context_pack(
    context_pack_id: str,
    current_user: str = Depends(require_auth),
):
    pack = context_pack_repo.get(context_pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Context pack not found")
    return pack


@router.post(
    "/projects/{project_id}/context-packs",
    response_model=ContextPack,
    status_code=201,
)
def create_pack(
    project_id: str,
    body: ContextPackCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return create_context_pack(
        context_pack_repo,
        project_id=project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        target_type=body.target_type,
        target_id=body.target_id,
        purpose=body.purpose,
        provider=body.provider,
        model=body.model,
        content_summary=body.content_summary,
        included_memory_ids=body.included_memory_ids,
        included_artifact_ids=body.included_artifact_ids,
        included_requirement_ids=body.included_requirement_ids,
        included_task_ids=body.included_task_ids,
        included_file_refs=body.included_file_refs,
        rules_summary=body.rules_summary,
        safety_summary=body.safety_summary,
        estimated_tokens_value=(
            body.estimated_tokens if body.estimated_tokens > 0 else None
        ),
        actual_input_tokens=body.actual_input_tokens,
        artifact_id=body.artifact_id,
        metadata=body.metadata,
    )
