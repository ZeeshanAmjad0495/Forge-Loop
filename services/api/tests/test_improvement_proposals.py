import pytest

from app.models import (
    ImprovementProposalCreate,
    ImprovementProposalUpdate,
)
from app.repositories import InMemoryImprovementProposalRepository
from app.services.improvement_proposals import (
    InvalidProposalTransition,
    approve_proposal,
    create_proposal,
    defer_proposal,
    mark_implemented,
    reject_proposal,
    update_proposal,
)


# -- service unit tests ---------------------------------------------------


def test_create_proposal_defaults():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo,
        body=ImprovementProposalCreate(title="Adopt OpenHands"),
    )
    assert proposal.status == "proposed"
    assert proposal.source_type == "manual"
    assert proposal.priority == "medium"
    assert repo.get(proposal.id) is proposal


def test_approve_then_implement_sets_timestamps():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t")
    )
    approved = approve_proposal(repo, proposal)
    assert approved.status == "approved"
    assert approved.approved_at is not None
    implemented = mark_implemented(repo, approved)
    assert implemented.status == "implemented"
    assert implemented.implemented_at is not None


def test_reject_records_reason_and_timestamp():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t")
    )
    rejected = reject_proposal(repo, proposal, reason="out of scope")
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "out of scope"
    assert rejected.rejected_at is not None


def test_defer_then_reopen_via_explicit_path():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t")
    )
    deferred = defer_proposal(repo, proposal)
    assert deferred.status == "deferred"
    # From deferred we may approve
    approved = approve_proposal(repo, deferred)
    assert approved.status == "approved"


def test_invalid_transition_from_proposed_to_implemented_blocked():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t")
    )
    with pytest.raises(InvalidProposalTransition):
        mark_implemented(repo, proposal)


def test_invalid_transition_from_archived_blocked():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t")
    )
    rejected = reject_proposal(repo, proposal)
    # rejected -> archived OK; archived -> anything blocked
    from app.services.improvement_proposals import archive_proposal

    archived = archive_proposal(repo, rejected)
    assert archived.status == "archived"
    with pytest.raises(InvalidProposalTransition):
        approve_proposal(repo, archived)


def test_update_proposal_modifies_fields():
    repo = InMemoryImprovementProposalRepository()
    proposal = create_proposal(
        repo, body=ImprovementProposalCreate(title="t", priority="low")
    )
    updated = update_proposal(
        repo,
        proposal,
        ImprovementProposalUpdate(
            priority="high",
            description="new description",
            affected_areas=["repo abstraction"],
        ),
    )
    assert updated.priority == "high"
    assert updated.description == "new description"
    assert updated.affected_areas == ["repo abstraction"]


# -- API tests ------------------------------------------------------------


def test_create_improvement_proposal_via_api(client):
    res = client.post(
        "/improvement-proposals",
        json={
            "title": "Adopt local Mongo",
            "proposal_type": "local_runtime",
            "priority": "high",
            "expected_benefit": "Faster local dev",
        },
    )
    assert res.status_code == 201
    assert res.json()["status"] == "proposed"


def test_list_filter_by_project_and_status(client, project):
    project_id = project["id"]
    client.post(
        "/improvement-proposals",
        json={"title": "a", "project_id": project_id},
    )
    other = client.post(
        "/improvement-proposals",
        json={"title": "b", "project_id": project_id},
    ).json()
    client.post(f"/improvement-proposals/{other['id']}/approve")

    by_project = client.get(
        f"/projects/{project_id}/improvement-proposals"
    ).json()
    assert len(by_project) == 2

    approved = client.get(
        f"/projects/{project_id}/improvement-proposals?status=approved"
    ).json()
    assert len(approved) == 1
    assert approved[0]["id"] == other["id"]


def test_full_lifecycle_via_api(client):
    created = client.post(
        "/improvement-proposals",
        json={"title": "t"},
    ).json()
    proposal_id = created["id"]

    approved = client.post(
        f"/improvement-proposals/{proposal_id}/approve"
    ).json()
    assert approved["status"] == "approved"

    implemented = client.post(
        f"/improvement-proposals/{proposal_id}/mark-implemented"
    ).json()
    assert implemented["status"] == "implemented"
    assert implemented["implemented_at"] is not None

    archived = client.post(
        f"/improvement-proposals/{proposal_id}/archive"
    ).json()
    assert archived["status"] == "archived"


def test_reject_with_reason_via_api(client):
    created = client.post(
        "/improvement-proposals", json={"title": "t"}
    ).json()
    res = client.post(
        f"/improvement-proposals/{created['id']}/reject",
        json={"reason": "out of scope"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "out of scope"


def test_invalid_state_transition_returns_409(client):
    created = client.post(
        "/improvement-proposals", json={"title": "t"}
    ).json()
    res = client.post(
        f"/improvement-proposals/{created['id']}/mark-implemented"
    )
    assert res.status_code == 409


def test_create_proposal_from_research_brief(client):
    brief = client.post("/research-briefs", json={"title": "b"}).json()
    res = client.post(
        f"/research-briefs/{brief['id']}/improvement-proposals",
        json={"title": "derived", "proposal_type": "quality_improvement"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["source_type"] == "research_brief"
    assert body["source_id"] == brief["id"]


def test_create_proposal_from_unknown_brief_404(client):
    res = client.post(
        "/research-briefs/missing/improvement-proposals",
        json={"title": "t"},
    )
    assert res.status_code == 404


def test_create_proposal_from_architecture_review(client):
    review = client.post(
        "/architecture-reviews",
        json={"title": "r", "target_type": "forge_loop"},
    ).json()
    res = client.post(
        f"/architecture-reviews/{review['id']}/improvement-proposals",
        json={"title": "derived"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["source_type"] == "architecture_review"
    assert body["source_id"] == review["id"]


def test_list_by_source(client):
    brief = client.post("/research-briefs", json={"title": "b"}).json()
    client.post(
        f"/research-briefs/{brief['id']}/improvement-proposals",
        json={"title": "p1"},
    )
    client.post("/improvement-proposals", json={"title": "p2"})

    filtered = client.get(
        f"/improvement-proposals?source_type=research_brief&source_id={brief['id']}"
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["title"] == "p1"
