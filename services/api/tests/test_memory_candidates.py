import os
import subprocess
import urllib.request

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_project(name: str = "CandProj") -> dict:
    return client.post("/projects", json={"name": name, "description": "d"}).json()


def _manual_candidate(
    project_id: str,
    *,
    memory_type: str = "known_failure_pattern",
    title: str = "Test phase regression after diff",
    content: str = "When CI fails in the test phase shortly after a code diff, suspect a regression in the changed module first.",
    tags: list[str] | None = None,
) -> dict:
    body = {
        "memory_type": memory_type,
        "title": title,
        "content": content,
        "tags": tags or ["ci", "regression"],
    }
    resp = client.post(f"/projects/{project_id}/memory-candidates", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Manual creation
# ---------------------------------------------------------------------------

def test_create_manual_candidate_returns_201_with_shape():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    assert cand["id"]
    assert cand["project_id"] == project["id"]
    assert cand["status"] == "proposed"
    assert cand["source_type"] == "manual"
    assert cand["source_id"] is None
    assert cand["memory_type"] == "known_failure_pattern"
    assert cand["learning_run_id"] is None
    assert cand["approved_at"] is None
    assert cand["rejected_at"] is None
    assert cand["rejection_reason"] is None


def test_create_manual_candidate_writes_audit_event():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = [(e["action"], e["target_id"]) for e in events]
    assert ("memory_candidate_created", cand["id"]) in actions


def test_create_manual_candidate_missing_project_returns_404():
    resp = client.post(
        "/projects/missing/memory-candidates",
        json={
            "memory_type": "known_risk",
            "title": "x",
            "content": "y",
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Listing / fetching
# ---------------------------------------------------------------------------

def test_list_project_candidates_returns_only_project_candidates():
    a = _create_project("A")
    b = _create_project("B")
    _manual_candidate(a["id"])
    _manual_candidate(a["id"])
    _manual_candidate(b["id"])

    resp = client.get(f"/projects/{a['id']}/memory-candidates")
    assert resp.status_code == 200
    cands = resp.json()
    assert len(cands) == 2
    assert all(c["project_id"] == a["id"] for c in cands)


def test_list_project_candidates_missing_project_returns_404():
    resp = client.get("/projects/missing/memory-candidates")
    assert resp.status_code == 404


def test_get_candidate_returns_one_and_404_on_missing():
    project = _create_project()
    cand = _manual_candidate(project["id"])

    ok = client.get(f"/memory-candidates/{cand['id']}")
    assert ok.status_code == 200
    assert ok.json()["id"] == cand["id"]

    miss = client.get("/memory-candidates/nope")
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------

def test_patch_candidate_updates_whitelisted_fields_while_proposed():
    project = _create_project()
    cand = _manual_candidate(project["id"])

    resp = client.patch(
        f"/memory-candidates/{cand['id']}",
        json={
            "title": "Updated title",
            "content": "Updated content",
            "tags": ["new"],
            "memory_type": "testing_rule",
            "confidence": 0.9,
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["title"] == "Updated title"
    assert updated["content"] == "Updated content"
    assert updated["tags"] == ["new"]
    assert updated["memory_type"] == "testing_rule"
    assert updated["confidence"] == 0.9
    assert updated["status"] == "proposed"
    assert updated["updated_at"] >= cand["updated_at"]


def test_patch_candidate_missing_returns_404():
    resp = client.patch("/memory-candidates/missing", json={"title": "x"})
    assert resp.status_code == 404


def test_patch_candidate_after_approval_returns_409():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/approve")

    resp = client.patch(
        f"/memory-candidates/{cand['id']}",
        json={"title": "Cannot edit"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def test_approve_candidate_writes_durable_project_memory():
    project = _create_project()
    cand = _manual_candidate(project["id"])

    resp = client.post(f"/memory-candidates/{cand['id']}/approve")
    assert resp.status_code == 200, resp.text
    approved = resp.json()
    assert approved["status"] == "approved"
    assert approved["approved_at"]

    # known_failure_pattern → safety_rules.
    ctx = client.get(f"/projects/{project['id']}/context").json()
    assert "safety_rules" in ctx
    assert f"[memory:{cand['id']}]" in ctx["safety_rules"]
    assert "known_failure_pattern" in ctx["safety_rules"]
    assert "Test phase regression" in ctx["safety_rules"]


def test_approve_candidate_appends_without_overwriting_existing_field():
    project = _create_project()
    # Seed pre-existing safety_rules content via the existing PUT context route.
    client.put(
        f"/projects/{project['id']}/context",
        json={
            "architecture_notes": "",
            "coding_standards": "",
            "test_commands": "",
            "deployment_commands": "",
            "domain_rules": "",
            "safety_rules": "EXISTING-LINE-DO-NOT-LOSE",
        },
    )
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/approve")

    ctx = client.get(f"/projects/{project['id']}/context").json()
    assert "EXISTING-LINE-DO-NOT-LOSE" in ctx["safety_rules"]
    assert f"[memory:{cand['id']}]" in ctx["safety_rules"]


def test_approve_candidate_targets_correct_field_per_memory_type():
    project = _create_project()
    arch = _manual_candidate(
        project["id"],
        memory_type="architecture_decision",
        title="Pick FastAPI for REST surface",
        content="The backend uses FastAPI for routing and Pydantic for request validation.",
    )
    rule = _manual_candidate(
        project["id"],
        memory_type="coding_standard",
        title="Prefer small functions",
        content="Functions should generally fit on one screen and have a single responsibility.",
    )
    client.post(f"/memory-candidates/{arch['id']}/approve")
    client.post(f"/memory-candidates/{rule['id']}/approve")

    ctx = client.get(f"/projects/{project['id']}/context").json()
    assert f"[memory:{arch['id']}]" in ctx["architecture_notes"]
    assert f"[memory:{rule['id']}]" in ctx["coding_standards"]
    assert f"[memory:{arch['id']}]" not in ctx["coding_standards"]
    assert f"[memory:{rule['id']}]" not in ctx["architecture_notes"]


def test_approve_candidate_writes_audit_events():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/approve")

    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("memory_candidate_approved", cand["id"]) in actions
    assert ("project_memory_learned", project["id"]) in actions


def test_approve_candidate_twice_returns_409():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    first = client.post(f"/memory-candidates/{cand['id']}/approve")
    assert first.status_code == 200

    second = client.post(f"/memory-candidates/{cand['id']}/approve")
    assert second.status_code == 409


def test_approve_candidate_missing_returns_404():
    resp = client.post("/memory-candidates/missing/approve")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------

def test_reject_candidate_with_reason():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    resp = client.post(
        f"/memory-candidates/{cand['id']}/reject",
        json={"reason": "duplicate of an existing rule"},
    )
    assert resp.status_code == 200, resp.text
    rejected = resp.json()
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "duplicate of an existing rule"
    assert rejected["rejected_at"]

    # Audit recorded.
    events = client.get(f"/projects/{project['id']}/audit-events").json()
    actions = {(e["action"], e["target_id"]) for e in events}
    assert ("memory_candidate_rejected", cand["id"]) in actions


def test_reject_candidate_without_body_works():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    resp = client.post(f"/memory-candidates/{cand['id']}/reject")
    assert resp.status_code == 200, resp.text
    assert resp.json()["rejection_reason"] is None


def test_reject_already_approved_candidate_returns_409():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/approve")
    resp = client.post(f"/memory-candidates/{cand['id']}/reject")
    assert resp.status_code == 409


def test_reject_already_rejected_candidate_returns_409():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/reject")
    resp = client.post(f"/memory-candidates/{cand['id']}/reject")
    assert resp.status_code == 409


def test_reject_candidate_missing_returns_404():
    resp = client.post("/memory-candidates/missing/reject")
    assert resp.status_code == 404


def test_approve_after_reject_returns_409():
    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.post(f"/memory-candidates/{cand['id']}/reject")
    resp = client.post(f"/memory-candidates/{cand['id']}/approve")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# No external calls
# ---------------------------------------------------------------------------

def test_candidate_endpoints_do_not_invoke_subprocess_or_network(monkeypatch):
    called: list[tuple] = []

    def fake_run(*args, **kwargs):
        called.append(("subprocess.run", args))
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_system(*args, **kwargs):
        called.append(("os.system", args))
        return 0

    def fake_urlopen(*args, **kwargs):
        called.append(("urlopen", args))
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "system", fake_system)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    project = _create_project()
    cand = _manual_candidate(project["id"])
    client.patch(f"/memory-candidates/{cand['id']}", json={"title": "edit"})
    client.post(f"/memory-candidates/{cand['id']}/approve")

    assert called == [], f"Unexpected external calls: {called}"
