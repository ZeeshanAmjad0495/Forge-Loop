"""Task 91 — per-dev-task execution lock.

Blocks the same dev task running concurrently (even across different
workspaces, which the per-workspace lock alone would miss). Non-blocking;
always released on success / failure / timeout.
"""

import pytest

from app.services.workspace_locks import (
    TaskBusyError,
    is_task_locked,
    task_execution_lock,
)


def test_same_task_concurrent_acquire_raises():
    with task_execution_lock("dt-1"):
        assert is_task_locked("dt-1")
        with pytest.raises(TaskBusyError):
            with task_execution_lock("dt-1"):
                pass


def test_different_tasks_do_not_contend():
    with task_execution_lock("dt-1"):
        with task_execution_lock("dt-2"):
            assert is_task_locked("dt-1")
            assert is_task_locked("dt-2")


def test_lock_released_after_success():
    with task_execution_lock("dt-1"):
        pass
    assert not is_task_locked("dt-1")
    # Re-acquire proves cleanup.
    with task_execution_lock("dt-1"):
        assert is_task_locked("dt-1")


def test_lock_released_after_exception():
    with pytest.raises(RuntimeError):
        with task_execution_lock("dt-1"):
            raise RuntimeError("boom")
    assert not is_task_locked("dt-1")
    with task_execution_lock("dt-1"):
        assert is_task_locked("dt-1")


def test_task_busy_error_carries_id():
    with task_execution_lock("dt-xyz"):
        try:
            with task_execution_lock("dt-xyz"):
                pass
            raise AssertionError("expected TaskBusyError")
        except TaskBusyError as e:
            assert e.dev_task_id == "dt-xyz"
