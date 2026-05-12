from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..models import (
    WorkflowTemplate,
    WorkflowTemplateCreate,
    WorkflowTemplatePreview,
    WorkflowTemplateUpdate,
)
from ..repositories_state import (
    audit_writer,
    workflow_template_repo,
)
from ..services.workflow_templates import (
    archive_template,
    build_preview,
    create_template,
    seed_defaults,
    update_template,
)

router = APIRouter()


def _get_or_404(template_id: str) -> WorkflowTemplate:
    template = workflow_template_repo.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return template


@router.post(
    "/workflow-templates", response_model=WorkflowTemplate, status_code=201
)
def create_workflow_template(
    body: WorkflowTemplateCreate,
    current_user: str = Depends(require_auth),
):
    if workflow_template_repo.get_by_slug(body.slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Slug already in use: {body.slug}"
        )
    template = create_template(workflow_template_repo, body=body)
    audit_writer.write(
        action="workflow_template_created",
        target_type="workflow_template",
        target_id=template.id,
        actor_email=current_user,
        details={"slug": template.slug, "workflow_type": template.workflow_type},
    )
    return template


@router.get("/workflow-templates", response_model=list[WorkflowTemplate])
def list_workflow_templates(
    status: str | None = None,
    workflow_type: str | None = None,
    active_only: bool = False,
    current_user: str = Depends(require_auth),
):
    items = workflow_template_repo.list_all()
    if active_only:
        items = [t for t in items if t.status == "active"]
    if status is not None:
        items = [t for t in items if t.status == status]
    if workflow_type is not None:
        items = [t for t in items if t.workflow_type == workflow_type]
    return items


@router.get(
    "/workflow-templates/by-slug/{slug}", response_model=WorkflowTemplate
)
def get_workflow_template_by_slug(
    slug: str, current_user: str = Depends(require_auth)
):
    template = workflow_template_repo.get_by_slug(slug)
    if template is None:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    return template


@router.get("/workflow-templates/{template_id}", response_model=WorkflowTemplate)
def get_workflow_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    return _get_or_404(template_id)


@router.patch(
    "/workflow-templates/{template_id}", response_model=WorkflowTemplate
)
def patch_workflow_template(
    template_id: str,
    body: WorkflowTemplateUpdate,
    current_user: str = Depends(require_auth),
):
    template = _get_or_404(template_id)
    updated = update_template(workflow_template_repo, template, body)
    audit_writer.write(
        action="workflow_template_updated",
        target_type="workflow_template",
        target_id=updated.id,
        actor_email=current_user,
    )
    return updated


@router.post(
    "/workflow-templates/{template_id}/archive",
    response_model=WorkflowTemplate,
)
def archive_workflow_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    template = _get_or_404(template_id)
    archived = archive_template(workflow_template_repo, template)
    audit_writer.write(
        action="workflow_template_archived",
        target_type="workflow_template",
        target_id=archived.id,
        actor_email=current_user,
    )
    return archived


@router.post(
    "/workflow-templates/seed-defaults",
    response_model=list[WorkflowTemplate],
)
def seed_default_workflow_templates(
    current_user: str = Depends(require_auth),
):
    seeded = seed_defaults(workflow_template_repo)
    audit_writer.write(
        action="workflow_templates_seeded",
        target_type="workflow_template",
        target_id="seed-defaults",
        actor_email=current_user,
        details={"count": len(seeded)},
    )
    return seeded


@router.post(
    "/workflow-templates/{template_id}/preview",
    response_model=WorkflowTemplatePreview,
)
def preview_workflow_template(
    template_id: str, current_user: str = Depends(require_auth)
):
    template = _get_or_404(template_id)
    return build_preview(template)
