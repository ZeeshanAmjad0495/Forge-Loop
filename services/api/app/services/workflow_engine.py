"""Task 80 (Phase A): WorkflowEngine abstraction + in-memory engine.

Foundation for long-running, human-supervised workflows. The in-memory
engine is dependency-free, deterministic, and the default used by tests.
A Temporal adapter is *designed for* but NOT implemented in Phase A —
selecting it fails fast and never imports `temporalio`.

This engine is ephemeral orchestration bookkeeping ONLY. It is not the
source of truth and must not bypass the existing repositories / audit
events: durable workflow effects (tickets, tasks, approvals, artifacts,
audit) are written by the workflow's steps through the normal
repositories — Phase C wiring, deliberately deferred here.

Human approval is an *explicit signal* (`HUMAN_APPROVAL_SIGNAL`), never
an implicit timeout or auto-progression.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .. import config as _config

# Candidate workflows (Task 80). Phase A registers the catalog; actual
# step logic / migration is Phase C and intentionally NOT implemented.
CANDIDATE_WORKFLOWS: tuple[str, ...] = (
    "requirement_to_plan",
    "plan_to_dev_tasks",
    "approved_dev_task_to_runner",
    "runner_result_to_pr_draft",
    "ci_failure_to_analysis",
    "incident_to_triage",
    "remediation_draft_to_approved_task",
)

HUMAN_APPROVAL_SIGNAL = "human_approval"

WorkflowStatus = Literal[
    "running",
    "waiting_human_approval",
    "completed",
    "cancelled",
    "failed",
]
_TERMINAL = ("completed", "cancelled", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowState(BaseModel):
    workflow_id: str
    workflow_type: str
    status: WorkflowStatus = "running"
    project_id: str | None = None
    input: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowEngine:
    """Abstract engine. Backends: in-memory (Phase A) / Temporal (Phase B)."""

    backend: str = "abstract"

    def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        input: dict | None = None,
        *,
        project_id: str | None = None,
        awaits_human_approval: bool = False,
    ) -> WorkflowState:
        raise NotImplementedError

    def signal_workflow(
        self, workflow_id: str, signal: str, payload: dict | None = None
    ) -> WorkflowState | None:
        raise NotImplementedError

    def get_workflow_status(self, workflow_id: str) -> WorkflowState | None:
        raise NotImplementedError

    def cancel_workflow(self, workflow_id: str) -> WorkflowState | None:
        raise NotImplementedError

    def health_check(self) -> dict:
        raise NotImplementedError


class InMemoryWorkflowEngine(WorkflowEngine):
    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._wf: dict[str, WorkflowState] = {}

    def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        input: dict | None = None,
        *,
        project_id: str | None = None,
        awaits_human_approval: bool = False,
    ) -> WorkflowState:
        if workflow_type not in CANDIDATE_WORKFLOWS:
            raise ValueError(
                f"Unknown workflow_type={workflow_type!r}. "
                f"Known: {', '.join(CANDIDATE_WORKFLOWS)}"
            )
        with self._lock:
            if workflow_id in self._wf:
                raise ValueError(
                    f"workflow_id={workflow_id!r} already exists"
                )
            now = _now()
            state = WorkflowState(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                status=(
                    "waiting_human_approval"
                    if awaits_human_approval
                    else "running"
                ),
                project_id=project_id,
                input=dict(input or {}),
                history=[{"at": now.isoformat(), "event": "started"}],
                created_at=now,
                updated_at=now,
            )
            self._wf[workflow_id] = state
            try:
                from .metrics import record_workflow_started

                record_workflow_started(workflow_type)
            except Exception:
                pass
            return state.model_copy(deep=True)

    def signal_workflow(
        self, workflow_id: str, signal: str, payload: dict | None = None
    ) -> WorkflowState | None:
        with self._lock:
            state = self._wf.get(workflow_id)
            if state is None:
                return None
            if state.status in _TERMINAL:
                return state.model_copy(deep=True)
            now = _now()
            state.history.append(
                {"at": now.isoformat(), "event": "signal", "signal": signal}
            )
            if signal == HUMAN_APPROVAL_SIGNAL:
                if state.status == "waiting_human_approval":
                    try:
                        from .metrics import observe_approval_wait

                        observe_approval_wait(
                            (now - state.created_at).total_seconds()
                        )
                    except Exception:
                        pass
                approved = bool((payload or {}).get("approved", False))
                state.status = "running" if approved else "cancelled"
                if not approved:
                    state.result = {"reason": "human_rejected"}
            state.updated_at = now
            return state.model_copy(deep=True)

    def get_workflow_status(self, workflow_id: str) -> WorkflowState | None:
        with self._lock:
            state = self._wf.get(workflow_id)
            return state.model_copy(deep=True) if state else None

    def cancel_workflow(self, workflow_id: str) -> WorkflowState | None:
        with self._lock:
            state = self._wf.get(workflow_id)
            if state is None:
                return None
            if state.status not in _TERMINAL:
                state.status = "cancelled"
                state.updated_at = _now()
                state.history.append(
                    {"at": state.updated_at.isoformat(), "event": "cancelled"}
                )
            return state.model_copy(deep=True)

    def health_check(self) -> dict:
        with self._lock:
            return {
                "backend": self.backend,
                "healthy": True,
                "active_workflows": sum(
                    1 for s in self._wf.values()
                    if s.status not in _TERMINAL
                ),
                "total_workflows": len(self._wf),
            }


_singleton_lock = threading.Lock()
_instance: WorkflowEngine | None = None


def _build() -> WorkflowEngine:
    sel = (_config.WORKFLOW_ENGINE_PROVIDER or "memory").strip().lower()
    if sel in ("memory", "inmemory", "local", ""):
        return InMemoryWorkflowEngine()
    if sel == "temporal":
        raise RuntimeError(
            "WORKFLOW_ENGINE_PROVIDER=temporal is a Phase B adapter and "
            "is not implemented yet (Task 80 Phase A ships the in-memory "
            "engine only). Use WORKFLOW_ENGINE_PROVIDER=memory."
        )
    raise RuntimeError(
        f"Unsupported WORKFLOW_ENGINE_PROVIDER={sel!r}. "
        "Supported: memory, temporal"
    )


def get_workflow_engine() -> WorkflowEngine:
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = _build()
    return _instance


def reset_workflow_engine() -> None:
    """Drop the singleton (clears workflow state). Test/process hook."""
    global _instance
    with _singleton_lock:
        _instance = None


def workflow_engine_runtime_summary() -> dict:
    engine = get_workflow_engine()
    try:
        health = engine.health_check()
    except Exception as exc:  # noqa: BLE001
        health = {"healthy": False, "error": type(exc).__name__}
    return {
        "configured_provider": (_config.WORKFLOW_ENGINE_PROVIDER or "memory"),
        "active_backend": engine.backend,
        "is_source_of_truth": False,
        "candidate_workflows": list(CANDIDATE_WORKFLOWS),
        "temporal_adapter": "designed_not_implemented_phase_b",
        "worker_enabled": _config.WORKER_ENABLED,
        "health": health,
    }


__all__ = [
    "WorkflowEngine",
    "InMemoryWorkflowEngine",
    "WorkflowState",
    "WorkflowStatus",
    "CANDIDATE_WORKFLOWS",
    "HUMAN_APPROVAL_SIGNAL",
    "get_workflow_engine",
    "reset_workflow_engine",
    "workflow_engine_runtime_summary",
]
