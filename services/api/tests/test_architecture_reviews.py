import json

from app.models import (
    ArchitectureReviewCreate,
    ArchitectureReviewGenerateRequest,
    ArchitectureReviewUpdate,
)
from app.repositories import (
    InMemoryArchitectureReviewRepository,
    InMemoryArtifactRepository,
)
from app.services.architecture_reviews import (
    archive_review,
    create_review,
    generate_review,
    update_review,
)


class _StubProvider:
    provider_name = "stub"
    model_name = "stub-model"

    def __init__(self, response: str):
        self._response = response
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


# -- service unit tests ---------------------------------------------------


def test_create_review_defaults():
    repo = InMemoryArchitectureReviewRepository()
    review = create_review(
        repo,
        body=ArchitectureReviewCreate(
            title="ForgeLoop architecture review",
            target_type="forge_loop",
        ),
    )
    assert review.status == "requested"
    assert review.target_type == "forge_loop"
    assert repo.get(review.id) is review


def test_update_review_to_completed_sets_completed_at():
    repo = InMemoryArchitectureReviewRepository()
    review = create_review(
        repo, body=ArchitectureReviewCreate(title="t")
    )
    updated = update_review(
        repo,
        review,
        ArchitectureReviewUpdate(
            status="completed",
            summary="ok",
            findings=["f"],
            recommendations=["r"],
            risks=["x"],
            score=0.8,
        ),
    )
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.summary == "ok"
    assert updated.score == 0.8


def test_archive_review_sets_status():
    repo = InMemoryArchitectureReviewRepository()
    review = create_review(
        repo, body=ArchitectureReviewCreate(title="t")
    )
    archived = archive_review(repo, review)
    assert archived.status == "archived"


def test_generate_review_parses_json():
    repo = InMemoryArchitectureReviewRepository()
    artifact_repo = InMemoryArtifactRepository()
    payload = json.dumps(
        {
            "summary": "Sound overall, minor risks.",
            "findings": ["repo abstraction is consistent"],
            "recommendations": ["document context routing"],
            "risks": ["scope creep on Studio modules"],
            "score": 0.75,
        }
    )
    provider = _StubProvider(payload)
    review, artifact = generate_review(
        repo,
        artifact_repo,
        provider,
        body=ArchitectureReviewGenerateRequest(
            title="ForgeLoop review",
            target_type="forge_loop",
            context="ForgeLoop has provider abstractions for repos and LLMs.",
        ),
    )
    assert review.status == "completed"
    assert review.findings == ["repo abstraction is consistent"]
    assert review.score == 0.75
    assert review.artifact_id == artifact.id
    assert "ARCHITECTURE_REVIEW_AGENT" in provider.prompts[0]


def test_generate_review_unparseable_marks_failed():
    repo = InMemoryArchitectureReviewRepository()
    artifact_repo = InMemoryArtifactRepository()
    provider = _StubProvider("nope")
    review, _ = generate_review(
        repo,
        artifact_repo,
        provider,
        body=ArchitectureReviewGenerateRequest(title="x"),
    )
    assert review.status == "failed"
    assert review.error_message


# -- API tests ------------------------------------------------------------


def test_create_architecture_review_via_api(client, project):
    res = client.post(
        "/architecture-reviews",
        json={
            "title": "Project review",
            "target_type": "project",
            "target_id": project["id"],
            "project_id": project["id"],
            "scope": "release 11 boundary",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["target_type"] == "project"
    assert body["target_id"] == project["id"]


def test_create_architecture_review_unknown_project_404(client):
    res = client.post(
        "/architecture-reviews",
        json={"title": "t", "project_id": "missing"},
    )
    assert res.status_code == 404


def test_list_architecture_reviews_filters(client, project):
    project_id = project["id"]
    client.post(
        "/architecture-reviews",
        json={
            "title": "a",
            "target_type": "project",
            "target_id": project_id,
            "project_id": project_id,
        },
    )
    client.post(
        "/architecture-reviews",
        json={"title": "b", "target_type": "forge_loop"},
    )

    all_items = client.get("/architecture-reviews").json()
    assert len(all_items) == 2

    forge = client.get(
        "/architecture-reviews?target_type=forge_loop"
    ).json()
    assert len(forge) == 1
    assert forge[0]["title"] == "b"

    by_target = client.get(
        f"/architecture-reviews?target_type=project&target_id={project_id}"
    ).json()
    assert len(by_target) == 1

    by_project = client.get(
        f"/projects/{project_id}/architecture-reviews"
    ).json()
    assert len(by_project) == 1


def test_patch_and_archive_architecture_review(client):
    created = client.post(
        "/architecture-reviews",
        json={"title": "t", "target_type": "forge_loop"},
    ).json()
    review_id = created["id"]

    patched = client.patch(
        f"/architecture-reviews/{review_id}",
        json={"summary": "complete", "status": "completed"},
    ).json()
    assert patched["status"] == "completed"
    assert patched["completed_at"] is not None

    archived = client.post(
        f"/architecture-reviews/{review_id}/archive"
    ).json()
    assert archived["status"] == "archived"


def test_get_missing_architecture_review_404(client):
    res = client.get("/architecture-reviews/missing")
    assert res.status_code == 404


def test_generate_architecture_review_with_mock_provider(client):
    res = client.post(
        "/architecture-reviews/generate?provider_name=mock",
        json={
            "title": "x",
            "target_type": "forge_loop",
            "context": "ForgeLoop overview...",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["provider"] == "mock"
    assert body["status"] in {"completed", "failed"}
