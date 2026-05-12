from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ProjectPack,
    ProjectPackCreate,
    ProjectPackPreview,
    ProjectPackUpdate,
)
from ..repositories_state import (
    audit_writer,
    project_pack_repo,
)
from ..services.project_packs import (
    archive_pack,
    build_preview,
    create_pack,
    seed_defaults,
    update_pack,
)

router = APIRouter()


def _get_or_404(pack_id: str) -> ProjectPack:
    pack = project_pack_repo.get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Project pack not found")
    return pack


@router.post("/project-packs", response_model=ProjectPack, status_code=201)
def create_project_pack(
    body: ProjectPackCreate,
    current_user: str = Depends(require_auth),
):
    if project_pack_repo.get_by_slug(body.slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Slug already in use: {body.slug}"
        )
    pack = create_pack(project_pack_repo, body=body)
    audit_writer.write(
        action="project_pack_created",
        target_type="project_pack",
        target_id=pack.id,
        actor_email=current_user,
        details={"slug": pack.slug, "domain": pack.domain},
    )
    return pack


@router.get("/project-packs", response_model=list[ProjectPack])
def list_project_packs(
    status: str | None = None,
    domain: str | None = None,
    active_only: bool = False,
    current_user: str = Depends(require_auth),
):
    items = project_pack_repo.list_all()
    if active_only:
        items = [p for p in items if p.status == "active"]
    if status is not None:
        items = [p for p in items if p.status == status]
    if domain is not None:
        items = [p for p in items if p.domain == domain]
    return items


@router.get("/project-packs/by-slug/{slug}", response_model=ProjectPack)
def get_project_pack_by_slug(
    slug: str, current_user: str = Depends(require_auth)
):
    pack = project_pack_repo.get_by_slug(slug)
    if pack is None:
        raise HTTPException(status_code=404, detail="Project pack not found")
    return pack


@router.get("/project-packs/{pack_id}", response_model=ProjectPack)
def get_project_pack(
    pack_id: str, current_user: str = Depends(require_auth)
):
    return _get_or_404(pack_id)


@router.patch("/project-packs/{pack_id}", response_model=ProjectPack)
def patch_project_pack(
    pack_id: str,
    body: ProjectPackUpdate,
    current_user: str = Depends(require_auth),
):
    pack = _get_or_404(pack_id)
    updated = update_pack(project_pack_repo, pack, body)
    audit_writer.write(
        action="project_pack_updated",
        target_type="project_pack",
        target_id=updated.id,
        actor_email=current_user,
    )
    return updated


@router.post("/project-packs/{pack_id}/archive", response_model=ProjectPack)
def archive_project_pack(
    pack_id: str, current_user: str = Depends(require_auth)
):
    pack = _get_or_404(pack_id)
    archived = archive_pack(project_pack_repo, pack)
    audit_writer.write(
        action="project_pack_archived",
        target_type="project_pack",
        target_id=archived.id,
        actor_email=current_user,
    )
    return archived


@router.post("/project-packs/seed-defaults", response_model=list[ProjectPack])
def seed_default_packs(
    current_user: str = Depends(require_auth),
):
    seeded = seed_defaults(project_pack_repo)
    audit_writer.write(
        action="project_packs_seeded",
        target_type="project_pack",
        target_id="seed-defaults",
        actor_email=current_user,
        details={"count": len(seeded)},
    )
    return seeded


@router.post(
    "/project-packs/{pack_id}/preview", response_model=ProjectPackPreview
)
def preview_project_pack(
    pack_id: str, current_user: str = Depends(require_auth)
):
    pack = _get_or_404(pack_id)
    return build_preview(pack)
