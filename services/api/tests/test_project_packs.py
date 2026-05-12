from app.models import ProjectPackCreate, ProjectPackUpdate
from app.repositories import InMemoryProjectPackRepository
from app.services.project_packs import (
    archive_pack,
    build_preview,
    create_pack,
    default_pack_slugs,
    seed_defaults,
    update_pack,
)


# -- service unit tests ---------------------------------------------------


def test_create_pack_defaults():
    repo = InMemoryProjectPackRepository()
    pack = create_pack(
        repo, body=ProjectPackCreate(name="x", slug="x", domain="devtools")
    )
    assert pack.status == "draft"
    assert pack.domain == "devtools"
    assert repo.get_by_slug("x") is pack


def test_seed_defaults_idempotent():
    repo = InMemoryProjectPackRepository()
    first = seed_defaults(repo)
    assert len(first) == len(default_pack_slugs())
    second = seed_defaults(repo)
    assert [p.id for p in first] == [p.id for p in second]


def test_archive_pack_sets_archived_at():
    repo = InMemoryProjectPackRepository()
    pack = create_pack(repo, body=ProjectPackCreate(name="x", slug="x"))
    archived = archive_pack(repo, pack)
    assert archived.status == "archived"
    assert archived.archived_at is not None


def test_update_pack_modifies_fields():
    repo = InMemoryProjectPackRepository()
    pack = create_pack(repo, body=ProjectPackCreate(name="x", slug="x"))
    updated = update_pack(
        repo,
        pack,
        ProjectPackUpdate(
            description="new",
            suggested_required_checks=["tests"],
            status="active",
        ),
    )
    assert updated.description == "new"
    assert updated.suggested_required_checks == ["tests"]
    assert updated.status == "active"


def test_build_preview_includes_suggestions():
    repo = InMemoryProjectPackRepository()
    seeded = seed_defaults(repo)
    ai = next(p for p in seeded if p.slug == "ai-assistant")
    preview = build_preview(ai)
    assert preview.pack.id == ai.id
    assert "tests" in preview.suggested_required_checks
    assert preview.suggested_model_routing.get("reason") == "deepseek"


# -- API tests ------------------------------------------------------------


def test_create_project_pack_via_api(client):
    res = client.post(
        "/project-packs",
        json={"name": "t", "slug": "t", "domain": "devtools"},
    )
    assert res.status_code == 201


def test_duplicate_slug_returns_409(client):
    client.post("/project-packs", json={"name": "t", "slug": "dup"})
    res = client.post("/project-packs", json={"name": "t2", "slug": "dup"})
    assert res.status_code == 409


def test_seed_defaults_via_api_is_idempotent(client):
    first = client.post("/project-packs/seed-defaults").json()
    second = client.post("/project-packs/seed-defaults").json()
    assert [p["id"] for p in first] == [p["id"] for p in second]
    all_packs = client.get("/project-packs").json()
    assert len(all_packs) == len(first)


def test_filter_by_domain(client):
    client.post("/project-packs/seed-defaults")
    qas = client.get("/project-packs?domain=qa_automation").json()
    assert len(qas) == 1


def test_get_by_slug(client):
    client.post("/project-packs/seed-defaults")
    res = client.get("/project-packs/by-slug/ai-assistant")
    assert res.status_code == 200
    assert res.json()["slug"] == "ai-assistant"


def test_patch_and_archive(client):
    created = client.post(
        "/project-packs", json={"name": "t", "slug": "t"}
    ).json()
    patched = client.patch(
        f"/project-packs/{created['id']}",
        json={"description": "new", "status": "active"},
    ).json()
    assert patched["status"] == "active"
    archived = client.post(f"/project-packs/{created['id']}/archive").json()
    assert archived["status"] == "archived"


def test_preview_endpoint(client):
    seeded = client.post("/project-packs/seed-defaults").json()
    target = next(p for p in seeded if p["slug"] == "ai-assistant")
    preview = client.post(f"/project-packs/{target['id']}/preview").json()
    assert preview["pack"]["slug"] == "ai-assistant"
    assert "reason" in preview["suggested_model_routing"]


def test_active_only_filter(client):
    client.post("/project-packs/seed-defaults")
    client.post(
        "/project-packs",
        json={"name": "d", "slug": "d-only", "status": "draft"},
    )
    actives = client.get("/project-packs?active_only=true").json()
    assert all(p["status"] == "active" for p in actives)
