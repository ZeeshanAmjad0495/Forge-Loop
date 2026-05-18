"""Per-workspace execution mutual exclusion (concurrency hardening).

ForgeLoop uses ONE git checkout per workspace and hard-syncs it (B1:
``git reset --hard`` + ``git clean -fd``) before every agent run. Two
executions in the *same* workspace therefore cannot safely overlap — one
run's sync would destroy the other's in-progress edits. Different
workspaces are fully independent and run concurrently with no contention.

This module enforces that guarantee instead of relying on callers to
serialize. ``workspace_execution_lock`` is a non-blocking per-workspace
mutex: a second concurrent execute() on the same workspace raises
``WorkspaceBusyError`` (-> HTTP 409) rather than racing.

Scope: in-process (the deployment runs a single uvicorn worker; sync route
handlers execute in Starlette's threadpool, so threads — not processes —
are the contention unit). A multi-worker / multi-host deployment would
need a distributed lock; that is intentionally out of scope and documented.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

_registry_lock = threading.Lock()
_held: set[str] = set()
# Task 91: a separate registry for per-dev-task mutual exclusion. Kept
# independent of the hardened workspace registry above (no refactor of a
# concurrency-critical primitive). Same in-process, single-worker scope
# and stale-lock behavior (the set resets on process restart).
_task_registry_lock = threading.Lock()
_task_held: set[str] = set()


class WorkspaceBusyError(RuntimeError):
    """Raised when an execution is already active for the workspace."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(
            f"workspace {workspace_id} already has an execution in progress"
        )
        self.workspace_id = workspace_id


class TaskBusyError(RuntimeError):
    """Raised when an execution is already active for the dev task.

    Task 91: blocks the *same* dev task running concurrently even across
    *different* workspaces (the per-workspace lock alone would miss that
    — two checkouts of the same task can still race shared task state).
    """

    def __init__(self, dev_task_id: str) -> None:
        super().__init__(
            f"dev task {dev_task_id} already has an execution in progress"
        )
        self.dev_task_id = dev_task_id


@contextmanager
def workspace_execution_lock(workspace_id: str):
    """Acquire the workspace's execution slot or raise WorkspaceBusyError.

    Non-blocking by design: callers should surface a 409 immediately rather
    than queue, so the operator/runner decides when to retry.
    """
    with _registry_lock:
        if workspace_id in _held:
            raise WorkspaceBusyError(workspace_id)
        _held.add(workspace_id)
    try:
        yield
    finally:
        with _registry_lock:
            _held.discard(workspace_id)


def is_locked(workspace_id: str) -> bool:
    with _registry_lock:
        return workspace_id in _held


@contextmanager
def task_execution_lock(dev_task_id: str):
    """Acquire the dev task's execution slot or raise TaskBusyError.

    Non-blocking, same semantics as ``workspace_execution_lock``. Always
    releases on success / failure / timeout via the ``finally`` below.
    """
    with _task_registry_lock:
        if dev_task_id in _task_held:
            raise TaskBusyError(dev_task_id)
        _task_held.add(dev_task_id)
    try:
        yield
    finally:
        with _task_registry_lock:
            _task_held.discard(dev_task_id)


def is_task_locked(dev_task_id: str) -> bool:
    with _task_registry_lock:
        return dev_task_id in _task_held


__all__ = [
    "WorkspaceBusyError",
    "TaskBusyError",
    "workspace_execution_lock",
    "task_execution_lock",
    "is_locked",
    "is_task_locked",
]
