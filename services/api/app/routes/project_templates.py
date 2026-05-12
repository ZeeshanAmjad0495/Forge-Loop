from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    ProjectTemplate,
    ProjectTemplateCreate,
    ProjectTemplatePreview,
    ProjectTemplateUpdate,
)
from ..repositories_state import (
    audit_writer,
    project_template_repo,
)
from ..services.project_templates import (
    archive_template,
    build_preview,
    create_template,
    list_active,
    seed_defaults,
    update_template,
)

router = APIRouter()


def _get_or_404(template_id: str) -> ProjectTemplate:
    template = project_template_repo.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Project template not found")
    return template


@router.post("/project-templates", response_model=ProjectTemplate, status_code=201)
def create_project_template(
    body: ProjectTemplateCreate,
    current_user: str = Depends(require_auth),
):
    if project_template_repo.get_by_slug(body.slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Slug already in use: {body.slug}"
        )
    template = create_template(project_template_repo, body=body)
    audit_writer.write(
        action="project_template_created",
        target_type="project_template",
        target_id=template.id,
        actor_email=current_user,
        details={"slug": template.slug, "template_type": template.template_type},
    )
    return template


@router.get("/project-templates", response_model=list[ProjectTemplate])
def list_project_templates(
    status: str | None = None,
    template_type: str | None = None,
    active_only: bool = False,
    current_user: str = Depends(require_auth),
):
    if active_only:
        items = list_active(project_template_repo)
    else:
        items = project_template_repo.list_all()
    if status is not None:
        items = [t for t in items if t.status == status]
    if template_type is not None:
        items = [t for t in items if t.template_type == template_type]
    return items


@router.get("/project-templates/by-slug/{slug}", response_model=ProjectTemplate)
def get_project_template_by_slug(
    slug: str, current_user: str = Depends(require_auth)
):
    template = project_template_repo.get_by_slug(slug)
    if template is None:
        raise HTTPException(status_code=404, detail="Project template not found")
    return template


@router.get("/project-templates/{template_id}", response_model=ProjectTemplate)
def get_project_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    return _get_or_404(template_id)


@router.patch("/project-templates/{template_id}", response_model=ProjectTemplate)
def patch_project_template(
    template_id: str,
    body: ProjectTemplateUpdate,
    current_user: str = Depends(require_auth),
):
    template = _get_or_404(template_id)
    updated = update_template(project_template_repo, template, body)
    audit_writer.write(
        action="project_template_updated",
        target_type="project_template",
        target_id=updated.id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/project-templates/{template_id}/archive",
    response_model=ProjectTemplate,
)
def archive_project_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    template = _get_or_404(template_id)
    archived = archive_template(project_template_repo, template)
    audit_writer.write(
        action="project_template_archived",
        target_type="project_template",
        target_id=archived.id,
        actor_email=current_user,
    )
    return archived


@router.post(
    "/project-templates/seed-defaults",
    response_model=list[ProjectTemplate],
)
def seed_default_templates(
    current_user: str = Depends(require_auth),
):
    seeded = seed_defaults(project_template_repo)
    audit_writer.write(
        action="project_templates_seeded",
        target_type="project_template",
        target_id="seed-defaults",
        actor_email=current_user,
        details={"count": len(seeded)},
    )
    return seeded


@router.post(
    "/project-templates/{template_id}/preview",
    response_model=ProjectTemplatePreview,
)
def preview_project_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    template = _get_or_404(template_id)
    return build_preview(template)
