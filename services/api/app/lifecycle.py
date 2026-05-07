from typing import Callable

from .models import DevTask, DevTaskStatus

ALLOWED_TRANSITIONS: dict[DevTaskStatus, set[DevTaskStatus]] = {
    "proposed": {"ready", "blocked"},
    "ready": {"in_progress", "blocked"},
    "in_progress": {"completed", "blocked"},
    "blocked": {"ready", "in_progress"},
    "completed": {"in_progress"},
}


class LifecycleError(Exception):
    pass


def validate_transition(current: DevTaskStatus, next_status: DevTaskStatus) -> None:
    if current == next_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if next_status not in allowed:
        raise LifecycleError(
            f"Invalid status transition: {current} -> {next_status}"
        )


def check_dependencies_completed(
    dev_task: DevTask,
    lookup: Callable[[str], DevTask | None],
) -> list[str]:
    blockers: list[str] = []
    for dep_id in dev_task.depends_on:
        dep = lookup(dep_id)
        if dep is None or dep.status != "completed":
            blockers.append(dep_id)
    return blockers


def compute_readiness(
    dev_task: DevTask,
    lookup: Callable[[str], DevTask | None],
) -> tuple[bool, list[str]]:
    blocked_by = check_dependencies_completed(dev_task, lookup)
    return len(blocked_by) == 0, blocked_by
