from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_auth
from ..lifecycle import LifecycleError, compute_readiness, validate_transition
from ..models import (
    CheckRun,
    CIEvent,
    DevTaskUpdate,
    DevTaskWithReadiness,
    DevTaskWithSubtasksResponse,
    ToolRun,
)
from ..repositories_state import (
    approval_repo,
    audit_writer,
    check_run_repo,
    ci_event_repo,
    dev_task_repo,
    project_repo,
    subtask_repo,
    tool_run_repo,
)

router = APIRouter()


def _with_readiness(dev_task) -> DevTaskWithReadiness:
    is_ready, blocked_by = compute_readiness(dev_task, dev_task_repo.get)
    return DevTaskWithReadiness(**dev_task.model_dump(), is_ready=is_ready, blocked_by=blocked_by)


@router.get("/projects/{project_id}/dev-tasks", response_model=list[DevTaskWithReadiness])
def list_project_dev_tasks(project_id: str, _: str = Depends(require_auth)):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return [_with_readiness(t) for t in dev_task_repo.list_by_project(project_id)]


@router.get("/dev-tasks/{dev_task_id}", response_model=DevTaskWithSubtasksResponse)
def get_dev_task(dev_task_id: str, _: str = Depends(require_auth)):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    subtasks = subtask_repo.list_by_dev_task(dev_task_id)
    return DevTaskWithSubtasksResponse(dev_task=_with_readiness(dev_task), subtasks=subtasks)


@router.patch("/dev-tasks/{dev_task_id}", response_model=DevTaskWithReadiness)
def update_dev_task(
    dev_task_id: str,
    body: DevTaskUpdate,
    current_user: str = Depends(require_auth),
):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    patch = body.model_dump(exclude_unset=True)
    new_status = patch.get("status")
    old_status = dev_task.status
    try:
        if new_status and new_status != dev_task.status:
            validate_transition(dev_task.status, new_status)
            if new_status in ("ready", "in_progress"):
                candidate = dev_task.model_copy(update=patch)
                blockers = compute_readiness(candidate, dev_task_repo.get)[1]
                if blockers:
                    raise LifecycleError(
                        f"Cannot move to {new_status}: dependencies not completed: {blockers}"
                    )
            if dev_task.status == "proposed" and new_status == "ready":
                approved = (
                    approval_repo.find_approved_for_target("dev_task", dev_task.id)
                    or approval_repo.find_approved_for_target("task_decomposition", dev_task.agent_run_id)
                )
                if approved is None:
                    raise HTTPException(
                        status_code=400,
                        detail="DevTask requires an approved approval before moving to ready",
                    )
    except LifecycleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    updated = dev_task.model_copy(
        update={**patch, "updated_at": datetime.now(timezone.utc)}
    )
    dev_task_repo.update(updated)
    if new_status and new_status != old_status:
        audit_writer.write(
            "dev_task_updated", "dev_task", dev_task.id,
            project_id=dev_task.project_id, actor_email=current_user,
            details={"from": old_status, "to": new_status},
        )
    assignment_fields = {"epic_id", "assignee_type", "assignee_id", "assignee_name"}
    changed_assignment = [f for f in assignment_fields if f in patch and getattr(dev_task, f) != patch[f]]
    if changed_assignment:
        audit_writer.write(
            "dev_task_assigned", "dev_task", dev_task.id,
            project_id=dev_task.project_id, actor_email=current_user,
            details={"changed_fields": changed_assignment},
        )
    return _with_readiness(updated)


@router.get("/dev-tasks/{dev_task_id}/subtasks", response_model=list)
def list_dev_task_subtasks(dev_task_id: str, _: str = Depends(require_auth)):
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return subtask_repo.list_by_dev_task(dev_task_id)


@router.get("/dev-tasks/{dev_task_id}/check-runs", response_model=list[CheckRun])
def list_dev_task_check_runs(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return check_run_repo.list_by_target("dev_task", dev_task_id)


@router.get("/dev-tasks/{dev_task_id}/tool-runs", response_model=list[ToolRun])
def list_dev_task_tool_runs(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return tool_run_repo.list_by_target("dev_task", dev_task_id)


@router.get("/dev-tasks/{dev_task_id}/ci-events", response_model=list[CIEvent])
def list_dev_task_ci_events(dev_task_id: str, _: str = Depends(require_auth)):
    if dev_task_repo.get(dev_task_id) is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    return ci_event_repo.list_by_dev_task(dev_task_id)
