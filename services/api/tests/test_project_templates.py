from app.models import ProjectTemplateCreate, ProjectTemplateUpdate
from app.repositories import InMemoryProjectTemplateRepository
from app.services.project_templates import (
    archive_template,
    build_preview,
    create_template,
    default_template_slugs,
    list_active,
    seed_defaults,
    update_template,
)


# -- service unit tests ---------------------------------------------------


def test_create_template_defaults():
    repo = InMemoryProjectTemplateRepository()
    t = create_template(
        repo,
        body=ProjectTemplateCreate(name="x", slug="x", template_type="backend_api"),
    )
    assert t.status == "draft"
    assert repo.get_by_slug("x") is t


def test_seed_defaults_idempotent():
    repo = InMemoryProjectTemplateRepository()
    first = seed_defaults(repo)
    assert len(first) == len(default_template_slugs())
    # second call returns same IDs (no duplicates)
    second = seed_defaults(repo)
    assert [t.id for t in first] == [t.id for t in second]
    assert len(repo.list_all()) == len(default_template_slugs())


def test_list_active_filters():
    repo = InMemoryProjectTemplateRepository()
    seed_defaults(repo)
    draft = create_template(
        repo,
        body=ProjectTemplateCreate(name="d", slug="d", status="draft"),
    )
    actives = list_active(repo)
    assert draft not in actives
    assert all(t.status == "active" for t in actives)


def test_archive_template_sets_archived_at():
    repo = InMemoryProjectTemplateRepository()
    t = create_template(
        repo, body=ProjectTemplateCreate(name="x", slug="x")
    )
    archived = archive_template(repo, t)
    assert archived.status == "archived"
    assert archived.archived_at is not None


def test_update_template_modifies_fields():
    repo = InMemoryProjectTemplateRepository()
    t = create_template(
        repo, body=ProjectTemplateCreate(name="x", slug="x")
    )
    updated = update_template(
        repo,
        t,
        ProjectTemplateUpdate(
            description="new", tags=["a"], stack=["python"], status="active"
        ),
    )
    assert updated.description == "new"
    assert updated.tags == ["a"]
    assert updated.stack == ["python"]
    assert updated.status == "active"


def test_build_preview_returns_suggested_values():
    repo = InMemoryProjectTemplateRepository()
    seeded = seed_defaults(repo)
    fastapi = next(t for t in seeded if t.slug == "fastapi-backend")
    preview = build_preview(fastapi)
    assert preview.template.id == fastapi.id
    assert "tests" in preview.suggested_required_checks
    assert ".env" in preview.suggested_blocked_paths


# -- API tests ------------------------------------------------------------


def test_create_project_template_via_api(client):
    res = client.post(
        "/project-templates",
        json={"name": "t", "slug": "t", "template_type": "cli_tool"},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "t"


def test_create_with_duplicate_slug_returns_409(client):
    client.post("/project-templates", json={"name": "t", "slug": "dup"})
    res = client.post(
        "/project-templates", json={"name": "t2", "slug": "dup"}
    )
    assert res.status_code == 409


def test_seed_defaults_via_api_is_idempotent(client):
    first = client.post("/project-templates/seed-defaults").json()
    second = client.post("/project-templates/seed-defaults").json()
    assert [t["id"] for t in first] == [t["id"] for t in second]
    all_templates = client.get("/project-templates").json()
    assert len(all_templates) == len(first)


def test_list_active_only(client):
    client.post("/project-templates/seed-defaults")
    client.post(
        "/project-templates",
        json={"name": "draft", "slug": "draft-only", "status": "draft"},
    )
    actives = client.get("/project-templates?active_only=true").json()
    assert all(t["status"] == "active" for t in actives)


def test_filter_by_template_type(client):
    client.post("/project-templates/seed-defaults")
    apis = client.get(
        "/project-templates?template_type=backend_api"
    ).json()
    assert len(apis) >= 1
    assert all(t["template_type"] == "backend_api" for t in apis)


def test_get_by_slug_endpoint(client):
    client.post("/project-templates/seed-defaults")
    res = client.get("/project-templates/by-slug/fastapi-backend")
    assert res.status_code == 200
    assert res.json()["slug"] == "fastapi-backend"


def test_get_by_unknown_slug_404(client):
    res = client.get("/project-templates/by-slug/missing")
    assert res.status_code == 404


def test_patch_and_archive_via_api(client):
    created = client.post(
        "/project-templates", json={"name": "t", "slug": "t"}
    ).json()
    patched = client.patch(
        f"/project-templates/{created['id']}",
        json={"status": "active", "description": "new"},
    ).json()
    assert patched["status"] == "active"
    archived = client.post(
        f"/project-templates/{created['id']}/archive"
    ).json()
    assert archived["status"] == "archived"
    assert archived["archived_at"] is not None


def test_preview_endpoint(client):
    seeded = client.post("/project-templates/seed-defaults").json()
    target = next(t for t in seeded if t["slug"] == "fastapi-backend")
    preview = client.post(
        f"/project-templates/{target['id']}/preview"
    ).json()
    assert preview["template"]["slug"] == "fastapi-backend"
    assert "tests" in preview["suggested_required_checks"]
