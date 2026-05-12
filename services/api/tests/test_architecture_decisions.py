import pytest

from app.models import (
    ArchitectureDecisionRecordCreate,
    ArchitectureDecisionRecordUpdate,
)
from app.repositories import InMemoryArchitectureDecisionRecordRepository
from app.services.architecture_decisions import (
    InvalidADRTransition,
    accept_adr,
    create_adr,
    deprecate_adr,
    reject_adr,
    supersede_adr,
    update_adr,
)


# -- service unit tests ---------------------------------------------------


def test_create_adr_defaults():
    repo = InMemoryArchitectureDecisionRecordRepository()
    adr = create_adr(
        repo,
        body=ArchitectureDecisionRecordCreate(title="ADR-001 Local-first storage"),
    )
    assert adr.status == "proposed"
    assert adr.decided_at is None
    assert repo.get(adr.id) is adr


def test_accept_adr_sets_decided_at():
    repo = InMemoryArchitectureDecisionRecordRepository()
    adr = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="t"))
    accepted = accept_adr(repo, adr)
    assert accepted.status == "accepted"
    assert accepted.decided_at is not None


def test_reject_adr_can_reopen():
    repo = InMemoryArchitectureDecisionRecordRepository()
    adr = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="t"))
    rejected = reject_adr(repo, adr)
    assert rejected.status == "rejected"
    # rejected -> proposed allowed (re-open)
    reopened_data = rejected.model_dump()
    reopened_data["status"] = "proposed"
    # validate transition via service
    from app.services.architecture_decisions import _transition

    reopened = _transition(repo, rejected, "proposed")
    assert reopened.status == "proposed"


def test_invalid_transition_from_proposed_to_deprecated():
    repo = InMemoryArchitectureDecisionRecordRepository()
    adr = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="t"))
    with pytest.raises(InvalidADRTransition):
        deprecate_adr(repo, adr)


def test_supersede_records_pointer():
    repo = InMemoryArchitectureDecisionRecordRepository()
    a = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="a"))
    b = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="b"))
    accepted = accept_adr(repo, a)
    superseded = supersede_adr(repo, accepted, superseded_by_id=b.id)
    assert superseded.status == "superseded"
    assert superseded.superseded_by_id == b.id


def test_update_adr_modifies_text_fields():
    repo = InMemoryArchitectureDecisionRecordRepository()
    adr = create_adr(repo, body=ArchitectureDecisionRecordCreate(title="t"))
    updated = update_adr(
        repo,
        adr,
        ArchitectureDecisionRecordUpdate(
            context="new context",
            decision="adopt X",
            consequences="must rewrite Y",
            tags=["local-first"],
        ),
    )
    assert updated.context == "new context"
    assert updated.decision == "adopt X"
    assert updated.tags == ["local-first"]


# -- API tests ------------------------------------------------------------


def test_create_adr_via_api(client):
    res = client.post(
        "/architecture-decisions",
        json={"title": "ADR-1", "decision": "adopt local-first"},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "proposed"


def test_accept_then_deprecate_via_api(client):
    created = client.post(
        "/architecture-decisions", json={"title": "t"}
    ).json()
    adr_id = created["id"]

    accepted = client.post(
        f"/architecture-decisions/{adr_id}/accept"
    ).json()
    assert accepted["status"] == "accepted"
    assert accepted["decided_at"] is not None

    deprecated = client.post(
        f"/architecture-decisions/{adr_id}/deprecate"
    ).json()
    assert deprecated["status"] == "deprecated"


def test_supersede_requires_existing_target(client):
    a = client.post("/architecture-decisions", json={"title": "a"}).json()
    client.post(f"/architecture-decisions/{a['id']}/accept")

    res = client.post(
        f"/architecture-decisions/{a['id']}/supersede",
        json={"superseded_by_id": "missing"},
    )
    assert res.status_code == 400

    b = client.post("/architecture-decisions", json={"title": "b"}).json()
    res = client.post(
        f"/architecture-decisions/{a['id']}/supersede",
        json={"superseded_by_id": b["id"]},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "superseded"
    assert res.json()["superseded_by_id"] == b["id"]


def test_invalid_transition_returns_409(client):
    created = client.post(
        "/architecture-decisions", json={"title": "t"}
    ).json()
    res = client.post(
        f"/architecture-decisions/{created['id']}/deprecate"
    )
    assert res.status_code == 409


def test_list_by_project_and_status(client, project):
    project_id = project["id"]
    client.post(
        "/architecture-decisions",
        json={"title": "a", "project_id": project_id},
    )
    other = client.post(
        "/architecture-decisions",
        json={"title": "b", "project_id": project_id, "tags": ["llm"]},
    ).json()
    client.post(f"/architecture-decisions/{other['id']}/accept")

    by_project = client.get(
        f"/projects/{project_id}/architecture-decisions"
    ).json()
    assert len(by_project) == 2

    by_status = client.get(
        f"/projects/{project_id}/architecture-decisions?status=accepted"
    ).json()
    assert len(by_status) == 1

    by_tag = client.get(
        f"/projects/{project_id}/architecture-decisions?tag=llm"
    ).json()
    assert len(by_tag) == 1


def test_create_adr_from_proposal(client):
    proposal = client.post(
        "/improvement-proposals", json={"title": "p"}
    ).json()
    res = client.post(
        f"/improvement-proposals/{proposal['id']}/architecture-decision",
        json={"title": "ADR from proposal"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["proposal_id"] == proposal["id"]


def test_create_adr_from_unknown_proposal_404(client):
    res = client.post(
        "/improvement-proposals/missing/architecture-decision",
        json={"title": "x"},
    )
    assert res.status_code == 404
