from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ResearchBrief,
    ResearchBriefCreate,
    ResearchBriefGenerateRequest,
    ResearchBriefUpdate,
)
from ..repositories_state import (
    artifact_repo,
    audit_writer,
    project_repo,
    research_brief_repo,
    research_source_repo,
)
from ..services.research_scout import (
    archive_brief,
    create_brief,
    generate_brief,
    update_brief,
)
from .common import resolve_routed_provider_or_400

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _validate_source_ids(source_ids: list[str]) -> None:
    for sid in source_ids:
        if research_source_repo.get(sid) is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown research_source: {sid}"
            )


@router.post(
    "/research-briefs",
    response_model=ResearchBrief,
    status_code=201,
)
def create_research_brief(
    body: ResearchBriefCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    _validate_source_ids(body.source_ids)
    brief = create_brief(research_brief_repo, body=body)
    audit_writer.write(
        action="research_brief_created",
        target_type="research_brief",
        target_id=brief.id,
        project_id=brief.project_id,
        actor_email=current_user,
        details={"research_type": brief.research_type, "status": brief.status},
    )
    return brief


@router.get("/research-briefs", response_model=list[ResearchBrief])
def list_research_briefs(
    project_id: str | None = None,
    research_type: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    if project_id is not None:
        _ensure_project(project_id)
        items = research_brief_repo.list_by_project(project_id)
    else:
        items = research_brief_repo.list_all()
    if research_type is not None:
        items = [b for b in items if b.research_type == research_type]
    if status is not None:
        items = [b for b in items if b.status == status]
    return items


@router.get(
    "/projects/{project_id}/research-briefs",
    response_model=list[ResearchBrief],
)
def list_research_briefs_for_project(
    project_id: str,
    research_type: str | None = None,
    status: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = research_brief_repo.list_by_project(project_id)
    if research_type is not None:
        items = [b for b in items if b.research_type == research_type]
    if status is not None:
        items = [b for b in items if b.status == status]
    return items


@router.get("/research-briefs/{brief_id}", response_model=ResearchBrief)
def get_research_brief(
    brief_id: str,
    current_user: str = Depends(require_auth),
):
    brief = research_brief_repo.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Research brief not found")
    return brief


@router.patch("/research-briefs/{brief_id}", response_model=ResearchBrief)
def patch_research_brief(
    brief_id: str,
    body: ResearchBriefUpdate,
    current_user: str = Depends(require_auth),
):
    brief = research_brief_repo.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Research brief not found")
    if body.source_ids is not None:
        _validate_source_ids(body.source_ids)
    updated = update_brief(research_brief_repo, brief, body)
    audit_writer.write(
        action="research_brief_updated",
        target_type="research_brief",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"status": updated.status},
    )
    return updated


@router.post("/research-briefs/{brief_id}/archive", response_model=ResearchBrief)
def archive_research_brief(
    brief_id: str,
    current_user: str = Depends(require_auth),
):
    brief = research_brief_repo.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Research brief not found")
    archived = archive_brief(research_brief_repo, brief)
    audit_writer.write(
        action="research_brief_archived",
        target_type="research_brief",
        target_id=archived.id,
        project_id=archived.project_id,
        actor_email=current_user,
    )
    return archived


@router.post("/research-briefs/generate", response_model=ResearchBrief, status_code=201)
def generate_research_brief(
    body: ResearchBriefGenerateRequest,
    provider_name: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    _validate_source_ids(body.source_ids)

    # Resolve source_summaries: caller-provided summaries take precedence;
    # otherwise fall back to summaries from the cached research sources.
    summaries = list(body.source_summaries)
    if not summaries and body.source_ids:
        for sid in body.source_ids:
            src = research_source_repo.get(sid)
            if src is not None and src.summary:
                summaries.append(src.summary)

    provider, _route_decision = resolve_routed_provider_or_400(
        "research",
        provider_name,
        project_id=body.project_id,
        source_type="research_brief",
    )

    brief, _artifact = generate_brief(
        research_brief_repo,
        artifact_repo,
        provider,
        body=body,
        source_summaries=summaries,
    )
    audit_writer.write(
        action="research_brief_generated",
        target_type="research_brief",
        target_id=brief.id,
        project_id=brief.project_id,
        actor_email=current_user,
        details={
            "research_type": brief.research_type,
            "status": brief.status,
            "provider": brief.provider,
            "model": brief.model,
        },
    )
    return brief
