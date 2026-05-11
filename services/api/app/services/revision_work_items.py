"""Task 39: RevisionWorkItem service.

Plan a revision from a ReviewFeedback, patch with status-transition
validator + approval gate. Execution itself flows through the existing
Task 36/37/38 endpoints; this service never invokes OpenHands, git, or
GitHub.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from ..models import (
    Artifact,
    RevisionPlanResponse,
    RevisionWorkItem,
    RevisionWorkItemCreate,
    RevisionWorkItemUpdate,
)


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"approved", "rejected"},
    "approved": {"in_progress", "rejected"},
    "in_progress": {"implemented", "rejected"},
    "implemented": {"checks_passed", "rejected"},
    "checks_passed": {"ready_for_review", "rejected"},
    "ready_for_review": {"resolved", "rejected"},
    "rejected": set(),
    "resolved": set(),
}


_TITLE_CAP = 240
_DESC_CAP = 4000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cap(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    s = str(text)
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def _default_title(feedback_id: str, summary: str) -> str:
    short = (summary or "").strip().splitlines()[0] if summary else ""
    short = short[:80]
    return _cap(f"Revision: address feedback {feedback_id[:8]} on {short}", _TITLE_CAP) or ""


def _default_description(feedback) -> str:
    parts = [
        f"Address review feedback `{feedback.id}` on PR draft `{feedback.pr_draft_id}`.",
        "",
        f"- **Severity:** {feedback.severity}",
        f"- **Category:** {feedback.category}",
    ]
    if feedback.file_path:
        line = f":{feedback.line}" if feedback.line is not None else ""
        parts.append(f"- **Location:** `{feedback.file_path}{line}`")
    if feedback.source:
        parts.append(f"- **Source:** {feedback.source}")
    parts.append("")
    parts.append("**Summary:**")
    parts.append(feedback.summary)
    if feedback.recommendation:
        parts.append("")
        parts.append("**Recommendation:**")
        parts.append(feedback.recommendation)
    parts.append("")
    parts.append(
        "Execute approved revisions through the existing Task 36 / 37 / 38 endpoints. "
        "Task 39 records traceability only."
    )
    return _cap("\n".join(parts), _DESC_CAP) or ""


@dataclass
class RevisionWorkItemService:
    review_feedback_repo: object
    revision_work_item_repo: object
    workspace_repo: object
    workspace_branch_repo: object
    dev_task_repo: object
    subtask_repo: object
    approval_repo: object
    project_repo: object
    artifact_repo: object
    audit_writer: object

    def _require_feedback(self, feedback_id: str):
        fb = self.review_feedback_repo.get(feedback_id)
        if fb is None:
            raise HTTPException(status_code=404, detail="ReviewFeedback not found")
        return fb

    def _require_revision(self, revision_id: str) -> RevisionWorkItem:
        item = self.revision_work_item_repo.get(revision_id)
        if item is None:
            raise HTTPException(status_code=404, detail="RevisionWorkItem not found")
        return item

    # --- public operations ------------------------------------------------

    def plan(
        self,
        feedback_id: str,
        body: RevisionWorkItemCreate,
        actor_email: str,
    ) -> RevisionPlanResponse:
        feedback = self._require_feedback(feedback_id)
        if feedback.status in ("resolved", "rejected"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"ReviewFeedback in status {feedback.status!r} cannot be used "
                    "to plan a revision"
                ),
            )

        workspace = self.workspace_repo.get(body.workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if workspace.project_id != feedback.project_id:
            raise HTTPException(
                status_code=400,
                detail="Workspace does not belong to feedback's project",
            )

        workspace_branch = None
        if body.workspace_branch_id:
            workspace_branch = self.workspace_branch_repo.get(body.workspace_branch_id)
            if workspace_branch is None:
                raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
            if workspace_branch.workspace_id != workspace.id:
                raise HTTPException(
                    status_code=400,
                    detail="WorkspaceBranch does not belong to selected workspace",
                )
            if workspace_branch.project_id != feedback.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="WorkspaceBranch does not belong to feedback's project",
                )
            if workspace_branch.status in ("failed", "archived"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"WorkspaceBranch is in status {workspace_branch.status!r}"
                    ),
                )

        if body.dev_task_id:
            dev_task = self.dev_task_repo.get(body.dev_task_id)
            if dev_task is None:
                raise HTTPException(status_code=404, detail="DevTask not found")
            if dev_task.project_id != feedback.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="DevTask does not belong to feedback's project",
                )

        if body.subtask_id:
            subtask = self.subtask_repo.get(body.subtask_id)
            if subtask is None:
                raise HTTPException(status_code=404, detail="Subtask not found")
            if subtask.project_id != feedback.project_id:
                raise HTTPException(
                    status_code=400,
                    detail="Subtask does not belong to feedback's project",
                )

        title = _cap((body.title or "").strip() or _default_title(feedback.id, feedback.summary), _TITLE_CAP) or ""
        description = _cap((body.description or "").strip() or _default_description(feedback), _DESC_CAP) or ""

        now = _now()
        item = RevisionWorkItem(
            id=str(uuid.uuid4()),
            project_id=feedback.project_id,
            pr_draft_id=feedback.pr_draft_id,
            review_feedback_id=feedback.id,
            dev_task_id=body.dev_task_id,
            subtask_id=body.subtask_id,
            workspace_id=workspace.id,
            workspace_branch_id=workspace_branch.id if workspace_branch else None,
            title=title,
            description=description,
            status="proposed",
            requires_approval=bool(body.approval_required),
            created_at=now,
            updated_at=now,
            approved_at=None,
            resolved_at=None,
        )
        self.revision_work_item_repo.save(item)

        updated_feedback = feedback.model_copy(update={
            "status": "revision_planned",
            "revision_work_item_id": item.id,
            "updated_at": now,
        })
        self.review_feedback_repo.save(updated_feedback)

        artifact_payload = json.dumps({
            "revision_work_item_id": item.id,
            "review_feedback_id": feedback.id,
            "pr_draft_id": feedback.pr_draft_id,
            "workspace_id": workspace.id,
            "workspace_branch_id": item.workspace_branch_id,
            "dev_task_id": item.dev_task_id,
            "subtask_id": item.subtask_id,
            "requires_approval": item.requires_approval,
        }, sort_keys=True)
        self.artifact_repo.save(Artifact(
            id=str(uuid.uuid4()),
            ticket_id=None,
            requirement_id=None,
            agent_run_id=None,
            artifact_type="revision_plan_summary",
            content=artifact_payload,
            created_at=now,
        ))
        self.audit_writer.write(
            "revision_work_item_planned",
            "revision_work_item",
            item.id,
            project_id=item.project_id,
            actor_email=actor_email,
            details={
                "review_feedback_id": feedback.id,
                "pr_draft_id": feedback.pr_draft_id,
                "workspace_id": workspace.id,
                "workspace_branch_id": item.workspace_branch_id,
                "requires_approval": item.requires_approval,
            },
        )

        return RevisionPlanResponse(
            review_feedback=updated_feedback,
            revision_work_item=item,
        )

    def list_by_pr_draft(self, pr_draft_id: str) -> list[RevisionWorkItem]:
        return self.revision_work_item_repo.list_by_pr_draft(pr_draft_id)

    def get(self, revision_id: str) -> RevisionWorkItem:
        return self._require_revision(revision_id)

    def patch(
        self,
        revision_id: str,
        body: RevisionWorkItemUpdate,
        actor_email: str,
    ) -> RevisionWorkItem:
        item = self._require_revision(revision_id)
        if item.status in ("resolved", "rejected"):
            raise HTTPException(
                status_code=400,
                detail=f"RevisionWorkItem in status {item.status!r} cannot be modified",
            )
        patch = body.model_dump(exclude_unset=True)
        if not patch:
            return item

        updates: dict = {}
        target_status: str | None = None
        if "status" in patch and patch["status"] is not None:
            target_status = patch["status"]
            if target_status != item.status and target_status not in _ALLOWED_TRANSITIONS.get(
                item.status, set()
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Disallowed status transition: {item.status} -> {target_status}"
                    ),
                )
            # Approval gate for proposed -> approved.
            if item.status == "proposed" and target_status == "approved" and item.requires_approval:
                approved = self.approval_repo.find_approved_for_target(
                    "revision_work_item", item.id
                )
                if approved is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "approval required for revision_work_item before "
                            "transitioning to approved"
                        ),
                    )
            updates["status"] = target_status
            if target_status == "approved":
                updates["approved_at"] = _now()
            if target_status == "resolved":
                updates["resolved_at"] = _now()

        if "title" in patch and patch["title"] is not None:
            updates["title"] = _cap(patch["title"].strip(), _TITLE_CAP) or item.title
        if "description" in patch and patch["description"] is not None:
            updates["description"] = _cap(patch["description"], _DESC_CAP) or ""
        if "workspace_branch_id" in patch:
            new_branch_id = patch["workspace_branch_id"]
            if new_branch_id is not None:
                branch = self.workspace_branch_repo.get(new_branch_id)
                if branch is None:
                    raise HTTPException(status_code=404, detail="WorkspaceBranch not found")
                if branch.workspace_id != item.workspace_id:
                    raise HTTPException(
                        status_code=400,
                        detail="WorkspaceBranch does not belong to revision workspace",
                    )
                if branch.status in ("failed", "archived"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"WorkspaceBranch is in status {branch.status!r}",
                    )
            updates["workspace_branch_id"] = new_branch_id

        updates["updated_at"] = _now()
        updated = item.model_copy(update=updates)
        self.revision_work_item_repo.save(updated)
        self.audit_writer.write(
            "revision_work_item_updated",
            "revision_work_item",
            updated.id,
            project_id=updated.project_id,
            actor_email=actor_email,
            details={
                "changed_fields": list(patch.keys()),
                "from_status": item.status,
                "to_status": target_status,
            },
        )
        return updated


def _service() -> RevisionWorkItemService:
    from ..repositories_state import (
        approval_repo,
        artifact_repo,
        audit_writer,
        dev_task_repo,
        project_repo,
        review_feedback_repo,
        revision_work_item_repo,
        subtask_repo,
        workspace_branch_repo,
        workspace_repo,
    )
    return RevisionWorkItemService(
        review_feedback_repo=review_feedback_repo,
        revision_work_item_repo=revision_work_item_repo,
        workspace_repo=workspace_repo,
        workspace_branch_repo=workspace_branch_repo,
        dev_task_repo=dev_task_repo,
        subtask_repo=subtask_repo,
        approval_repo=approval_repo,
        project_repo=project_repo,
        artifact_repo=artifact_repo,
        audit_writer=audit_writer,
    )


def plan(feedback_id, body, actor_email):
    return _service().plan(feedback_id, body, actor_email)


def list_by_pr_draft(pr_draft_id):
    return _service().list_by_pr_draft(pr_draft_id)


def get(revision_id):
    return _service().get(revision_id)


def patch(revision_id, body, actor_email):
    return _service().patch(revision_id, body, actor_email)


__all__ = [
    "RevisionWorkItemService",
    "get",
    "list_by_pr_draft",
    "patch",
    "plan",
]
