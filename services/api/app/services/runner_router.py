"""Task 77: RunnerRouter.

Chooses the fastest safe runner for a coding task. OpenHands is NOT the
default — it is reserved for broad multi-file / complex repo work and is
approval-gated. Pure decision logic (mirrors services/model_routing.py):
it never invokes a runner; execution stays gated by the *_ENABLED flags
and the existing OpenHands/Aider execute endpoints.

Runner order: deterministic -> lightweight -> aider -> openhands.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .. import config

RunnerName = Literal["deterministic", "lightweight", "aider", "openhands"]
RuntimeClass = Literal["tiny", "small", "medium", "large"]
Complexity = Literal["tiny", "small", "medium", "large"]
RiskLevel = Literal["low", "medium", "high"]

_ORDER: dict[str, int] = {"tiny": 0, "small": 1, "medium": 2, "large": 3}
_CHEAPEST_FALLBACK: dict[RunnerName, RunnerName | None] = {
    "openhands": "aider",
    "aider": "lightweight",
    "lightweight": "deterministic",
    "deterministic": None,
}
_DOC_TEST_TYPES = {
    "docs", "documentation", "doc", "test", "tests", "testing",
}
_CHECK_TYPES = {"check", "qa", "lint", "typecheck", "ci"}


class RunnerRoutePreviewRequest(BaseModel):
    task_type: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    estimated_files: int = 1
    multi_file: bool = False
    complexity: Complexity | None = None  # explicit hint wins
    risk_level: RiskLevel = "low"
    # Explicit opt-in for OpenHands (e.g. task requests it / human approved).
    allow_openhands: bool = False
    openhands_approved: bool = False


class RunnerRouteDecision(BaseModel):
    runner_name: RunnerName
    reason: str
    requires_human_approval: bool = False
    estimated_runtime_class: RuntimeClass
    task_complexity: Complexity
    risk_level: RiskLevel
    allowed_commands_profile: str
    fallback_runner: RunnerName | None = None
    warnings: list[str] = []


_PROFILE: dict[RunnerName, str] = {
    "deterministic": "qa_checks_only",
    "lightweight": "instruction_only_no_exec",
    "aider": "local_codegen",
    "openhands": "broad_repo_write",
}


def _derive_complexity(req: RunnerRoutePreviewRequest) -> Complexity:
    if req.complexity:
        return req.complexity
    tt = (req.task_type or "").strip().lower()
    if tt in _DOC_TEST_TYPES or tt in _CHECK_TYPES:
        return "tiny"
    if req.multi_file or req.estimated_files > 3:
        return "large"
    if req.estimated_files > 1:
        return "medium"
    return "small"


def decide_runner(
    request: RunnerRoutePreviewRequest,
) -> RunnerRouteDecision:
    warnings: list[str] = []
    risk = request.risk_level
    requires_approval = risk == "high"
    if requires_approval:
        warnings.append("high_risk_requires_human_approval")

    complexity = _derive_complexity(request)
    runtime = complexity  # 1:1 mapping is sufficient & predictable

    if not config.RUNNER_ROUTING_ENABLED:
        runner: RunnerName = config.DEFAULT_CODING_RUNNER  # type: ignore[assignment]
        reason = "runner_routing_disabled_use_default"
        return RunnerRouteDecision(
            runner_name=runner, reason=reason,
            requires_human_approval=requires_approval,
            estimated_runtime_class=runtime, task_complexity=complexity,
            risk_level=risk, allowed_commands_profile=_PROFILE.get(
                runner, "instruction_only_no_exec"),
            fallback_runner=_CHEAPEST_FALLBACK.get(runner),
            warnings=warnings,
        )

    tt = (request.task_type or "").strip().lower()

    # 1) deterministic for pure check/qa/lint/script work.
    if tt in _CHECK_TYPES:
        runner, reason = "deterministic", "check_qa_only_workflow"
    # 2) docs/test-only or tiny -> lightweight (no OpenHands).
    elif tt in _DOC_TEST_TYPES or complexity == "tiny":
        runner = (
            "lightweight" if config.LIGHTWEIGHT_RUNNER_ENABLED
            else "aider"
        )
        reason = "docs_or_test_or_tiny_no_openhands"
    # 3) small single-area coding -> lightweight (default coding runner).
    elif complexity == "small":
        runner = config.DEFAULT_CODING_RUNNER  # type: ignore[assignment]
        if runner == "lightweight" and not config.LIGHTWEIGHT_RUNNER_ENABLED:
            runner = "aider"
        reason = "small_change_default_coding_runner"
    else:
        # 4) medium/large: OpenHands is ELIGIBLE only at/above the min
        # complexity AND only when explicitly allowed/auto-select on.
        oh_eligible = _ORDER[complexity] >= _ORDER.get(
            config.OPENHANDS_MIN_COMPLEXITY, 2
        )
        wants_oh = (
            config.OPENHANDS_AUTO_SELECT_ENABLED or request.allow_openhands
        )
        if oh_eligible and wants_oh:
            if (
                config.OPENHANDS_REQUIRE_APPROVAL
                and not request.openhands_approved
            ):
                # Blocked: do not auto-run OpenHands; fall back, flag it.
                requires_approval = True
                warnings.append("openhands_requires_approval_fell_back")
                runner = "aider"
                reason = "openhands_blocked_pending_approval_fallback_aider"
            else:
                runner = "openhands"
                reason = "broad_multifile_openhands_allowed"
                if config.OPENHANDS_REQUIRE_APPROVAL:
                    requires_approval = True
        else:
            runner = "aider"
            reason = (
                "multifile_but_openhands_not_auto_selected_use_aider"
            )
            if oh_eligible:
                warnings.append(
                    "openhands_eligible_but_not_allowed_set_allow_openhands"
                )

    return RunnerRouteDecision(
        runner_name=runner,  # type: ignore[arg-type]
        reason=reason,
        requires_human_approval=requires_approval,
        estimated_runtime_class=runtime,
        task_complexity=complexity,
        risk_level=risk,
        allowed_commands_profile=_PROFILE.get(
            runner, "instruction_only_no_exec"
        ),
        fallback_runner=_CHEAPEST_FALLBACK.get(runner),  # type: ignore[arg-type]
        warnings=warnings,
    )


class RunnerRouteRejected(Exception):
    """Task 90: the RunnerRouter refused this execution request — e.g. a
    narrow task asked for OpenHands without human approval, or the router
    selected a no-code-generation runner (deterministic)."""


# DevTask.task_type -> router request. documentation/testing already
# live in _DOC_TEST_TYPES (router -> tiny). The multi-file-ish types get
# a multi_file hint so the router can consider OpenHands.
_MULTIFILE_TASK_TYPES = {"full_stack", "infrastructure", "refactor"}


def _dev_task_to_request(
    dev_task, requested_runner: str, approved: bool
) -> RunnerRoutePreviewRequest:
    task_type = getattr(dev_task, "task_type", "unknown") or "unknown"
    description = getattr(dev_task, "description", "") or ""
    multi_file = task_type in _MULTIFILE_TASK_TYPES or len(description) > 1200
    return RunnerRoutePreviewRequest(
        task_type=task_type,
        source_type="dev_task",
        source_id=getattr(dev_task, "id", None),
        estimated_files=3 if multi_file else 1,
        multi_file=multi_file,
        allow_openhands=(requested_runner == "openhands"),
        openhands_approved=approved,
    )


def enforce_runner_route(
    dev_task, requested_runner: str, *, approved: bool
) -> RunnerRouteDecision:
    """Task 90: mandatory RunnerRouter gate for real coding execution.

    The RunnerRouter is consulted (and its decision recorded by the
    caller) for every execution. OpenHands is never auto-selected for
    narrow tasks (``decide_runner`` guarantees this). A direct OpenHands
    request the router would route elsewhere is permitted ONLY when the
    run is human-approved (the approval is the documented broad/complex
    justification) — and the override is recorded. A no-code-generation
    (``deterministic``) selection is always blocked for a code-execution
    request.
    """
    decision = decide_runner(
        _dev_task_to_request(dev_task, requested_runner, approved)
    )
    if not config.RUNNER_ROUTER_ENFORCED:
        decision.warnings.append("runner_router_enforcement_disabled")
        return decision

    if decision.runner_name == "deterministic":
        raise RunnerRouteRejected(
            "RUNNER_ROUTER_REJECTED: router selected a non-code-generation "
            "runner (deterministic) for this execution request"
        )
    if decision.requires_human_approval and not approved:
        raise RunnerRouteRejected(
            "RUNNER_ROUTER_REJECTED: this task requires human approval "
            "before runner execution"
        )
    if requested_runner == "openhands" and decision.runner_name != "openhands":
        if not approved:
            raise RunnerRouteRejected(
                f"RUNNER_ROUTER_REJECTED: router selected "
                f"{decision.runner_name!r}; OpenHands is reserved for "
                f"broad/complex, human-approved work"
            )
        decision.warnings.append(
            f"runner_router_preferred_{decision.runner_name}_"
            f"overridden_by_human_approval"
        )
    return decision


def runner_routing_summary() -> dict:
    return {
        "enabled": config.RUNNER_ROUTING_ENABLED,
        "default_coding_runner": config.DEFAULT_CODING_RUNNER,
        "openhands_auto_select_enabled": config.OPENHANDS_AUTO_SELECT_ENABLED,
        "openhands_require_approval": config.OPENHANDS_REQUIRE_APPROVAL,
        "openhands_min_complexity": config.OPENHANDS_MIN_COMPLEXITY,
        "lightweight_runner_enabled": config.LIGHTWEIGHT_RUNNER_ENABLED,
        "runner_max_parallel_local": config.RUNNER_MAX_PARALLEL_LOCAL,
        "runner_order": ["deterministic", "lightweight", "aider", "openhands"],
    }


__all__ = [
    "RunnerName",
    "RunnerRoutePreviewRequest",
    "RunnerRouteDecision",
    "RunnerRouteRejected",
    "decide_runner",
    "enforce_runner_route",
    "runner_routing_summary",
]
