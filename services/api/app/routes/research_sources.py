from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ResearchBrief,
    ResearchSource,
    ResearchSourceCreate,
    ResearchSourceUpdate,
)
from ..repositories_state import (
    audit_writer,
    project_repo,
    research_brief_repo,
    research_source_repo,
)
from ..services.research_sources import (
    attach_source_to_brief,
    create_source,
    update_source,
)

router = APIRouter()


def _ensure_project(project_id: str | None) -> None:
    if project_id is None:
        return
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/research-sources", response_model=ResearchSource, status_code=201)
def create_research_source(
    body: ResearchSourceCreate,
    current_user: str = Depends(require_auth),
):
    _ensure_project(body.project_id)
    source = create_source(research_source_repo, body=body)
    audit_writer.write(
        action="research_source_created",
        target_type="research_source",
        target_id=source.id,
        project_id=source.project_id,
        actor_email=current_user,
        details={"source_type": source.source_type},
    )
    return source


@router.get("/research-sources", response_model=list[ResearchSource])
def list_research_sources(
    project_id: str | None = None,
    source_type: str | None = None,
    trust_level: str | None = None,
    tag: str | None = None,
    current_user: str = Depends(require_auth),
):
    if project_id is not None:
        _ensure_project(project_id)
        items = research_source_repo.list_by_project(project_id)
    else:
        items = research_source_repo.list_all()
    if source_type is not None:
        items = [s for s in items if s.source_type == source_type]
    if trust_level is not None:
        items = [s for s in items if s.trust_level == trust_level]
    if tag is not None:
        items = [s for s in items if tag in s.tags]
    return items


@router.get(
    "/projects/{project_id}/research-sources",
    response_model=list[ResearchSource],
)
def list_research_sources_for_project(
    project_id: str,
    source_type: str | None = None,
    trust_level: str | None = None,
    tag: str | None = None,
    current_user: str = Depends(require_auth),
):
    _ensure_project(project_id)
    items = research_source_repo.list_by_project(project_id)
    if source_type is not None:
        items = [s for s in items if s.source_type == source_type]
    if trust_level is not None:
        items = [s for s in items if s.trust_level == trust_level]
    if tag is not None:
        items = [s for s in items if tag in s.tags]
    return items


@router.get("/research-sources/{source_id}", response_model=ResearchSource)
def get_research_source(
    source_id: str,
    current_user: str = Depends(require_auth),
):
    source = research_source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Research source not found")
    return source


@router.patch("/research-sources/{source_id}", response_model=ResearchSource)
def patch_research_source(
    source_id: str,
    body: ResearchSourceUpdate,
    current_user: str = Depends(require_auth),
):
    source = research_source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Research source not found")
    updated = update_source(research_source_repo, source, body)
    audit_writer.write(
        action="research_source_updated",
        target_type="research_source",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/research-briefs/{brief_id}/sources/{source_id}",
    response_model=ResearchBrief,
)
def attach_source(
    brief_id: str,
    source_id: str,
    current_user: str = Depends(require_auth),
):
    brief = research_brief_repo.get(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Research brief not found")
    if research_source_repo.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Research source not found")
    updated = attach_source_to_brief(research_brief_repo, brief, source_id)
    audit_writer.write(
        action="research_brief_updated",
        target_type="research_brief",
        target_id=updated.id,
        project_id=updated.project_id,
        actor_email=current_user,
        details={"attached_source_id": source_id},
    )
    return updated
