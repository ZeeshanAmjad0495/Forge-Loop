from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..lifecycle import LifecycleError, validate_transition
from ..models import SubtaskUpdate, ToolRun
from ..repositories_state import audit_writer, subtask_repo, tool_run_repo

router = APIRouter()


@router.patch("/subtasks/{subtask_id}")
def update_subtask(
    subtask_id: str,
    body: SubtaskUpdate,
    current_user: str = Depends(require_auth),
):
    subtask = subtask_repo.get(subtask_id)
    if subtask is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    old_status = subtask.status
    if new_status and new_status != subtask.status:
        try:
            validate_transition(subtask.status, new_status)
        except LifecycleError as e:
            raise HTTPException(status_code=400, detail=str(e))
    updated = subtask.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    subtask_repo.update(updated)
    if new_status and new_status != old_status:
        audit_writer.write(
            "subtask_updated", "subtask", subtask.id,
            project_id=subtask.project_id, actor_email=current_user,
            details={"from": old_status, "to": new_status},
        )
    subtask_assignment_fields = {"assignee_type", "assignee_id", "assignee_name"}
    changed_subtask_assignment = [f for f in subtask_assignment_fields if f in patch and getattr(subtask, f) != patch[f]]
    if changed_subtask_assignment:
        audit_writer.write(
            "subtask_assigned", "subtask", subtask.id,
            project_id=subtask.project_id, actor_email=current_user,
            details={"changed_fields": changed_subtask_assignment},
        )
    return updated


@router.get("/subtasks/{subtask_id}/tool-runs", response_model=list[ToolRun])
def list_subtask_tool_runs(subtask_id: str, _: str = Depends(require_auth)):
    if subtask_repo.get(subtask_id) is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    return tool_run_repo.list_by_target("subtask", subtask_id)
