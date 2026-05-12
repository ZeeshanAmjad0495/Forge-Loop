import json

from app.models import (
    ProjectRetrospectiveCreate,
    ProjectRetrospectiveUpdate,
)
from app.repositories import (
    InMemoryArtifactRepository,
    InMemoryProjectRetrospectiveRepository,
)
from app.services.retrospectives import (
    archive_retrospective,
    create_retrospective,
    generate_retrospective,
    update_retrospective,
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


def test_create_retrospective_defaults():
    repo = InMemoryProjectRetrospectiveRepository()
    retro = create_retrospective(
        repo,
        project_id="p1",
        body=ProjectRetrospectiveCreate(title="trial-1 retro"),
    )
    assert retro.project_id == "p1"
    assert retro.status == "draft"


def test_update_retrospective_completed_sets_completed_at():
    repo = InMemoryProjectRetrospectiveRepository()
    retro = create_retrospective(
        repo, project_id="p1", body=ProjectRetrospectiveCreate(title="t")
    )
    updated = update_retrospective(
        repo,
        retro,
        ProjectRetrospectiveUpdate(
            status="completed",
            summary="ok",
            what_worked=["fast iteration"],
            what_failed=["over-scope"],
        ),
    )
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.what_worked == ["fast iteration"]


def test_archive_retrospective_sets_archived_status():
    repo = InMemoryProjectRetrospectiveRepository()
    retro = create_retrospective(
        repo, project_id="p1", body=ProjectRetrospectiveCreate(title="t")
    )
    archived = archive_retrospective(repo, retro)
    assert archived.status == "archived"


def test_generate_retrospective_parses_json():
    repo = InMemoryProjectRetrospectiveRepository()
    artifact_repo = InMemoryArtifactRepository()
    payload = json.dumps(
        {
            "summary": "Trial completed with strong quality signals.",
            "what_worked": ["repo abstraction"],
            "what_failed": ["over-scope on Studio"],
            "quality_notes": "no regressions",
            "cost_notes": "within budget",
            "feedback_themes": ["clarity"],
            "failure_themes": ["scope drift"],
            "decisions": ["adopt local-first"],
            "recommendations": ["lock scope earlier"],
        }
    )
    provider = _StubProvider(payload)
    retro, artifact = generate_retrospective(
        repo,
        artifact_repo,
        provider,
        project_id="p1",
        trial_id="t1",
        title="trial-1",
        summary_inputs="trial outcome data...",
    )
    assert retro.status == "generated"
    assert retro.what_worked == ["repo abstraction"]
    assert retro.decisions == ["adopt local-first"]
    assert retro.artifact_id == artifact.id
    assert "PROJECT_RETROSPECTIVE_AGENT" in provider.prompts[0]


def test_generate_retrospective_unparseable_marks_failed():
    repo = InMemoryProjectRetrospectiveRepository()
    artifact_repo = InMemoryArtifactRepository()
    provider = _StubProvider("not json")
    retro, _ = generate_retrospective(
        repo,
        artifact_repo,
        provider,
        project_id="p1",
        trial_id=None,
        title="t",
        summary_inputs="",
    )
    assert retro.status == "failed"
    assert retro.error_message


# -- API tests ------------------------------------------------------------


def test_create_retrospective_via_api(client, project):
    project_id = project["id"]
    res = client.post(
        f"/projects/{project_id}/retrospectives",
        json={"title": "Trial retrospective"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["project_id"] == project_id
    assert body["status"] == "draft"


def test_create_retrospective_unknown_project_404(client):
    res = client.post(
        "/projects/missing/retrospectives",
        json={"title": "t"},
    )
    assert res.status_code == 404


def test_create_retrospective_unknown_trial_400(client, project):
    res = client.post(
        f"/projects/{project['id']}/retrospectives",
        json={"title": "t", "trial_id": "missing"},
    )
    assert res.status_code == 400


def test_list_retrospectives_filters_by_trial(client, project):
    project_id = project["id"]
    trial = client.post(
        f"/projects/{project_id}/build-trials",
        json={"name": "trial-1"},
    ).json()
    client.post(
        f"/projects/{project_id}/retrospectives",
        json={"title": "linked", "trial_id": trial["id"]},
    )
    client.post(
        f"/projects/{project_id}/retrospectives",
        json={"title": "unlinked"},
    )

    all_retros = client.get(
        f"/projects/{project_id}/retrospectives"
    ).json()
    assert len(all_retros) == 2

    by_trial = client.get(
        f"/projects/{project_id}/retrospectives?trial_id={trial['id']}"
    ).json()
    assert len(by_trial) == 1
    assert by_trial[0]["title"] == "linked"


def test_patch_and_archive_retrospective(client, project):
    project_id = project["id"]
    created = client.post(
        f"/projects/{project_id}/retrospectives",
        json={"title": "t"},
    ).json()
    retro_id = created["id"]

    patched = client.patch(
        f"/retrospectives/{retro_id}",
        json={"summary": "done", "status": "completed"},
    ).json()
    assert patched["status"] == "completed"
    assert patched["completed_at"] is not None

    archived = client.post(
        f"/retrospectives/{retro_id}/archive"
    ).json()
    assert archived["status"] == "archived"


def test_generate_retrospective_for_trial_with_mock_provider(client, project):
    project_id = project["id"]
    trial = client.post(
        f"/projects/{project_id}/build-trials",
        json={"name": "trial-1"},
    ).json()
    res = client.post(
        f"/build-trials/{trial['id']}/retrospective/generate?provider_name=mock",
        json={"title": "Trial retro", "summary_inputs": "ran a trial"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["provider"] == "mock"
    assert body["trial_id"] == trial["id"]
    assert body["status"] in {"generated", "failed"}


def test_generate_retrospective_unknown_trial_404(client):
    res = client.post(
        "/build-trials/missing/retrospective/generate",
        json={"summary_inputs": "x"},
    )
    assert res.status_code == 404


def test_create_proposal_from_retrospective(client, project):
    project_id = project["id"]
    retro = client.post(
        f"/projects/{project_id}/retrospectives",
        json={"title": "t"},
    ).json()
    res = client.post(
        f"/retrospectives/{retro['id']}/improvement-proposals",
        json={"title": "follow-up"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["source_type"] == "retrospective"
    assert body["source_id"] == retro["id"]

    # retrospective is back-linked
    refreshed = client.get(f"/retrospectives/{retro['id']}").json()
    assert body["id"] in refreshed["proposal_ids"]
