import uuid
from datetime import datetime, timezone

from app.models import ReviewFeedback, RevisionWorkItem
from app.repositories_state import (
    review_feedback_repo,
    revision_work_item_repo,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _feedback(
    project_id: str,
    pr_draft_id: str = "d",
    severity: str = "blocking",
    status: str = "open",
    category: str = "correctness",
    source: str = "human",
) -> ReviewFeedback:
    return ReviewFeedback(
        id=str(uuid.uuid4()),
        project_id=project_id,
        pr_draft_id=pr_draft_id,
        source=source,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        summary="x",
        created_at=_now(),
        updated_at=_now(),
    )


def _revision(
    project_id: str,
    pr_draft_id: str = "d",
    status: str = "proposed",
) -> RevisionWorkItem:
    return RevisionWorkItem(
        id=str(uuid.uuid4()),
        project_id=project_id,
        pr_draft_id=pr_draft_id,
        review_feedback_id="rf",
        workspace_id="w",
        title="t",
        description="d",
        status=status,  # type: ignore[arg-type]
        created_at=_now(),
        updated_at=_now(),
    )


def test_empty_project_analytics(client, project):
    res = client.get(f"/projects/{project['id']}/feedback-analytics")
    assert res.status_code == 200
    m = res.json()["metrics"]
    assert m["total_feedback_items"] == 0
    assert m["category_counts"] == {}
    assert m["revision_items_created"] == 0


def test_project_analytics_counts_severities_and_categories(client, project):
    project_id = project["id"]
    review_feedback_repo.save(_feedback(project_id, severity="blocking", category="correctness"))
    review_feedback_repo.save(_feedback(project_id, severity="warning", category="tests"))
    review_feedback_repo.save(
        _feedback(project_id, severity="info", category="tests", status="resolved")
    )
    revision_work_item_repo.save(_revision(project_id))
    revision_work_item_repo.save(_revision(project_id, status="resolved"))

    res = client.get(f"/projects/{project_id}/feedback-analytics").json()
    m = res["metrics"]
    assert m["total_feedback_items"] == 3
    assert m["blocking_count"] == 1
    assert m["warning_count"] == 1
    assert m["info_count"] == 1
    assert m["resolved_feedback_items"] == 1
    assert m["category_counts"]["tests"] == 2
    assert m["revision_items_created"] == 2
    assert m["revision_items_resolved"] == 1


def test_pr_draft_analytics_filters_by_draft(client, project, pr_draft):
    project_id = project["id"]
    draft_id = pr_draft["id"]
    review_feedback_repo.save(_feedback(project_id, pr_draft_id=draft_id))
    review_feedback_repo.save(_feedback(project_id, pr_draft_id="other"))
    res = client.get(f"/pr-drafts/{draft_id}/feedback-analytics").json()
    assert res["metrics"]["total_feedback_items"] == 1


def test_pr_draft_analytics_unknown_draft(client):
    res = client.get("/pr-drafts/missing/feedback-analytics")
    assert res.status_code == 404


def test_project_analytics_unknown_project(client):
    res = client.get("/projects/missing/feedback-analytics")
    assert res.status_code == 404
