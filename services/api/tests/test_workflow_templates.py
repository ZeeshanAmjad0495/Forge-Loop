from app.models import (
    WorkflowStage,
    WorkflowTemplateCreate,
    WorkflowTemplateUpdate,
)
from app.repositories import InMemoryWorkflowTemplateRepository
from app.services.workflow_templates import (
    archive_template,
    build_preview,
    create_template,
    default_template_slugs,
    seed_defaults,
    update_template,
)


# -- service unit tests ---------------------------------------------------


def test_create_template_persists_stages():
    repo = InMemoryWorkflowTemplateRepository()
    t = create_template(
        repo,
        body=WorkflowTemplateCreate(
            name="x",
            slug="x",
            stages=[WorkflowStage(name="plan", stage_type="planning")],
        ),
    )
    assert t.status == "draft"
    assert t.stages[0].name == "plan"


def test_seed_defaults_idempotent():
    repo = InMemoryWorkflowTemplateRepository()
    first = seed_defaults(repo)
    assert len(first) == len(default_template_slugs())
    second = seed_defaults(repo)
    assert [t.id for t in first] == [t.id for t in second]


def test_archive_template_sets_archived_at():
    repo = InMemoryWorkflowTemplateRepository()
    t = create_template(
        repo, body=WorkflowTemplateCreate(name="x", slug="x")
    )
    archived = archive_template(repo, t)
    assert archived.status == "archived"
    assert archived.archived_at is not None


def test_update_template_modifies_fields():
    repo = InMemoryWorkflowTemplateRepository()
    t = create_template(
        repo, body=WorkflowTemplateCreate(name="x", slug="x")
    )
    updated = update_template(
        repo,
        t,
        WorkflowTemplateUpdate(
            description="new",
            default_required_checks=["tests"],
            status="active",
        ),
    )
    assert updated.description == "new"
    assert updated.default_required_checks == ["tests"]
    assert updated.status == "active"


def test_build_preview_returns_stages_and_checks():
    repo = InMemoryWorkflowTemplateRepository()
    seeded = seed_defaults(repo)
    feature = next(t for t in seeded if t.slug == "feature")
    preview = build_preview(feature)
    assert preview.template.id == feature.id
    assert any(s.stage_type == "planning" for s in preview.stages)
    assert "tests" in preview.required_checks


# -- API tests ------------------------------------------------------------


def test_create_workflow_template_via_api(client):
    res = client.post(
        "/workflow-templates",
        json={"name": "t", "slug": "t", "workflow_type": "feature"},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "t"


def test_duplicate_slug_returns_409(client):
    client.post("/workflow-templates", json={"name": "t", "slug": "dup"})
    res = client.post("/workflow-templates", json={"name": "t2", "slug": "dup"})
    assert res.status_code == 409


def test_seed_defaults_via_api_is_idempotent(client):
    first = client.post("/workflow-templates/seed-defaults").json()
    second = client.post("/workflow-templates/seed-defaults").json()
    assert [t["id"] for t in first] == [t["id"] for t in second]
    all_templates = client.get("/workflow-templates").json()
    assert len(all_templates) == len(first)


def test_filter_by_workflow_type(client):
    client.post("/workflow-templates/seed-defaults")
    features = client.get("/workflow-templates?workflow_type=feature").json()
    assert len(features) == 1
    assert features[0]["slug"] == "feature"


def test_active_only_filter(client):
    client.post("/workflow-templates/seed-defaults")
    client.post(
        "/workflow-templates",
        json={"name": "d", "slug": "d-only", "status": "draft"},
    )
    actives = client.get("/workflow-templates?active_only=true").json()
    assert all(t["status"] == "active" for t in actives)


def test_get_by_slug(client):
    client.post("/workflow-templates/seed-defaults")
    res = client.get("/workflow-templates/by-slug/feature")
    assert res.status_code == 200
    assert res.json()["slug"] == "feature"


def test_patch_and_archive(client):
    created = client.post(
        "/workflow-templates", json={"name": "t", "slug": "t"}
    ).json()
    patched = client.patch(
        f"/workflow-templates/{created['id']}",
        json={"description": "new", "status": "active"},
    ).json()
    assert patched["status"] == "active"
    archived = client.post(
        f"/workflow-templates/{created['id']}/archive"
    ).json()
    assert archived["status"] == "archived"


def test_preview_endpoint(client):
    seeded = client.post("/workflow-templates/seed-defaults").json()
    feature = next(t for t in seeded if t["slug"] == "feature")
    preview = client.post(
        f"/workflow-templates/{feature['id']}/preview"
    ).json()
    assert preview["template"]["slug"] == "feature"
    assert len(preview["stages"]) > 0
