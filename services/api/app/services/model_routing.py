"""Model routing policy.

Selects a provider/model for a workflow without calling any provider.

#46 hardening — Kimi (the EXPENSIVE provider) is no longer an automatic
routing target. Policy:
  1. Local-first for cheap/simple workflows (Ollama when enabled).
  2. DeepSeek (NORMAL_REASONING_PROVIDER) is the normal hosted fallback.
  3. Kimi only when expensive use is explicitly allowed AND approved
     (or a dedicated auto-fallback flag is set). Default: blocked.
  4. Long context recommends context reduction before any expensive
     provider; never auto-selects Kimi.
  5. High risk requires human approval but routes to DeepSeek, not Kimi.
  6. Every decision records why (reason, fallback_chain, warnings,
     expensive_provider_blocked, context_reduction_recommended).
Provider/model defaults are the single registry in ``app.llm``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .. import config
from ..llm import _PROVIDER_REGISTRY, get_default_provider_name, get_provider_by_name
from ..llm.base import LLMProvider

WorkflowType = Literal[
    "analysis", "planning", "coding", "review", "qa", "ci", "incident",
    "memory", "compression", "research", "manual", "custom",
    "requirement_analysis", "task_decomposition", "implementation_planning",
    "pr_review", "ci_analysis", "incident_analysis", "artifact_summary",
    "memory_extraction", "classification", "long_context_review",
    "high_risk", "test", "smoke", "demo",
]

RiskLevel = Literal["low", "medium", "high"]


class ModelRoutePreviewRequest(BaseModel):
    workflow_type: WorkflowType
    source_type: str | None = None
    source_id: str | None = None
    estimated_context_tokens: int = 0
    risk_level: RiskLevel = "low"
    override_provider: str | None = None
    override_model: str | None = None
    # #46: caller must explicitly opt in to an expensive provider, and an
    # approval/budget flag must be present (unless approval is disabled).
    allow_expensive_provider: bool = False
    expensive_approved: bool = False


class ModelRouteDecision(BaseModel):
    workflow_type: WorkflowType
    project_id: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    selected_provider: str
    selected_model: str
    reason: str
    fallback_provider: str | None = None
    fallback_model: str | None = None
    fallback_chain: list[str] = []
    estimated_context_tokens: int = 0
    risk_level: RiskLevel = "low"
    requires_human_approval: bool = False
    expensive_provider_blocked: bool = False
    context_reduction_recommended: bool = False
    warnings: list[str] = []


_LOCAL_WORKFLOWS = {
    "artifact_summary", "memory_extraction", "memory", "compression",
    "classification",
}
_REASONING_WORKFLOWS = {
    "analysis", "planning", "coding", "review", "ci", "incident", "qa",
    "research", "requirement_analysis", "task_decomposition",
    "implementation_planning", "pr_review", "ci_analysis",
    "incident_analysis",
}
_TEST_WORKFLOWS = {"test", "smoke", "demo"}


def _long_context(estimated_tokens: int) -> bool:
    return estimated_tokens >= config.MODEL_ROUTING_LONG_CONTEXT_TOKENS


def _model_for(provider: str) -> str:
    """Single source of truth = the app.llm provider registry (keeps
    routing model defaults consistent with the provider layer)."""
    if provider in _PROVIDER_REGISTRY:
        return config.LLM_MODEL or _PROVIDER_REGISTRY[provider]["default_model"]
    if (
        provider == config.OPENAI_COMPATIBLE_PROVIDER_NAME
        and config.OPENAI_COMPATIBLE_ENABLED
    ):
        return config.OPENAI_COMPATIBLE_MODEL or "gpt-4o-mini"
    return config.LLM_MODEL or "default"


def _expensive_allowed(request: ModelRoutePreviewRequest) -> bool:
    """Kimi/expensive is permitted only when explicitly requested AND
    approved (or approval is globally disabled), or the dedicated
    auto-fallback flag is on."""
    if config.KIMI_AUTO_FALLBACK_ENABLED:
        return True
    if not request.allow_expensive_provider:
        return False
    if not config.KIMI_REQUIRE_APPROVAL:
        return True
    return request.expensive_approved


def _is_expensive(provider: str) -> bool:
    return provider == config.EXPENSIVE_PROVIDER


def decide_route(
    request: ModelRoutePreviewRequest,
    project_id: str | None = None,
) -> ModelRouteDecision:
    warnings: list[str] = []
    state = {"expensive_blocked": False}
    context_reduction = False
    requires_human_approval = False
    NORMAL = config.NORMAL_REASONING_PROVIDER
    LOCAL = config.LOCAL_CHEAP_PROVIDER

    def _finish(provider, reason, *, fb=None, extra_warn=None):
        # Final guard: never emit the expensive provider unless allowed.
        if _is_expensive(provider) and not _expensive_allowed(request):
            state["expensive_blocked"] = True
            warnings.append("expensive_provider_blocked_routed_to_normal")
            provider = NORMAL
            reason = f"{reason}__expensive_blocked"
        chain: list[str] = [provider]
        if fb and fb != provider and not (
            _is_expensive(fb) and not _expensive_allowed(request)
        ):
            chain.append(fb)
        for w in extra_warn or []:
            warnings.append(w)
        is_override = reason == "explicit_override"
        return ModelRouteDecision(
            workflow_type=request.workflow_type,
            project_id=project_id,
            source_type=request.source_type,
            source_id=request.source_id,
            selected_provider=provider,
            selected_model=(
                request.override_model or _model_for(provider)
                if is_override else _model_for(provider)
            ),
            reason=reason,
            fallback_provider=chain[1] if len(chain) > 1 else None,
            fallback_model=_model_for(chain[1]) if len(chain) > 1 else None,
            fallback_chain=chain,
            estimated_context_tokens=request.estimated_context_tokens,
            risk_level=request.risk_level,
            requires_human_approval=requires_human_approval,
            expensive_provider_blocked=state["expensive_blocked"],
            context_reduction_recommended=context_reduction,
            warnings=warnings,
        )

    # Explicit override — still subject to the expensive guard.
    if request.override_provider:
        if _is_expensive(request.override_provider) and not _expensive_allowed(
            request
        ):
            requires_human_approval = True
            return _finish(
                request.override_provider, "explicit_override",
                extra_warn=["override_expensive_requires_approval"],
            )
        return _finish(request.override_provider, "explicit_override")

    if not config.MODEL_ROUTING_ENABLED:
        return _finish(
            config.LLM_PROVIDER, "routing_disabled_use_global_llm_provider"
        )

    workflow = request.workflow_type
    long_ctx = _long_context(request.estimated_context_tokens)

    if workflow in _TEST_WORKFLOWS:
        return _finish(config.TEST_PROVIDER, "test_smoke_demo_workflow")

    if workflow in _LOCAL_WORKFLOWS:
        if config.MODEL_ROUTING_PREFER_LOCAL and config.OLLAMA_ENABLED:
            return _finish(LOCAL, "local_first_workflow_ollama", fb=NORMAL)
        return _finish(
            NORMAL, "local_workflow_ollama_unavailable_fallback_normal",
            extra_warn=["ollama_disabled_falling_back_to_deepseek_not_kimi"],
        )

    if workflow == "long_context_review" or long_ctx:
        if config.MODEL_ROUTING_CONTEXT_REDUCTION_FIRST:
            context_reduction = True
            warnings.append("context_reduction_recommended_before_expensive")
        if _expensive_allowed(request):
            return _finish(
                config.EXPENSIVE_PROVIDER,
                "long_context_expensive_explicitly_allowed", fb=NORMAL,
            )
        return _finish(
            NORMAL, "long_context_no_expensive_use_normal",
            extra_warn=["long_context_not_routed_to_kimi_by_default"],
        )

    if workflow == "high_risk" or request.risk_level == "high":
        requires_human_approval = True
        if _expensive_allowed(request):
            return _finish(
                config.EXPENSIVE_PROVIDER,
                "high_risk_expensive_explicitly_allowed", fb=NORMAL,
            )
        return _finish(
            NORMAL, "high_risk_requires_approval_routed_normal",
            extra_warn=["high_risk_not_routed_to_kimi_by_default"],
        )

    if workflow in _REASONING_WORKFLOWS:
        fb = config.EXPENSIVE_PROVIDER if _expensive_allowed(request) else None
        return _finish(NORMAL, "default_reasoning_workflow", fb=fb)

    return _finish(
        NORMAL, "default_unknown_workflow_uses_normal_reasoning",
        extra_warn=["unrecognized_workflow_type"],
    )


def routing_summary() -> dict:
    return {
        "enabled": config.MODEL_ROUTING_ENABLED,
        "normal_reasoning_provider": config.NORMAL_REASONING_PROVIDER,
        "local_cheap_provider": config.LOCAL_CHEAP_PROVIDER,
        "expensive_provider": config.EXPENSIVE_PROVIDER,
        "test_provider": config.TEST_PROVIDER,
        "long_context_threshold_tokens": config.MODEL_ROUTING_LONG_CONTEXT_TOKENS,
        "prefer_local": config.MODEL_ROUTING_PREFER_LOCAL,
        "context_reduction_first": config.MODEL_ROUTING_CONTEXT_REDUCTION_FIRST,
        "kimi_auto_fallback_enabled": config.KIMI_AUTO_FALLBACK_ENABLED,
        "kimi_require_approval": config.KIMI_REQUIRE_APPROVAL,
        "ollama_enabled": config.OLLAMA_ENABLED,
        "openai_compatible_enabled": config.OPENAI_COMPATIBLE_ENABLED,
        # Legacy keys kept for existing runtime-endpoint consumers.
        "default_reasoning_provider": config.NORMAL_REASONING_PROVIDER,
        "long_context_provider": config.EXPENSIVE_PROVIDER,
        "local_support_provider": config.LOCAL_CHEAP_PROVIDER,
        "routing_enforced": config.MODEL_ROUTING_ENFORCED,
    }


class RoutedProviderError(Exception):
    """Raised when routing policy refuses to hand back a provider —
    e.g. an expensive provider that the route decision blocked. This is
    a defense-in-depth invariant: ``decide_route`` already reroutes a
    blocked expensive provider to the normal reasoning provider, so this
    should never fire on the normal path."""


def resolve_routed_provider(
    workflow_type: WorkflowType,
    *,
    provider_override: str | None = None,
    project_id: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    estimated_context_tokens: int = 0,
    risk_level: RiskLevel = "low",
    allow_expensive_provider: bool = False,
    expensive_approved: bool = False,
) -> tuple[LLMProvider, ModelRouteDecision]:
    """The single enforced entrypoint for real LLM execution.

    Every route/service that needs an ``LLMProvider`` for a real model
    call must resolve it here. The provider is chosen by
    ``decide_route`` (the ModelRouter), never by the caller. A
    per-request ``provider_override`` is honored only insofar as the
    route decision allows it — an expensive (Kimi) override is gated by
    the same approval/budget policy as automatic routing.

    Provider instantiation uses the ``app.llm`` factory (factory
    internals may name a concrete adapter — that is the only allowed
    direct provider selection).

    Returns ``(provider, decision)`` so callers (and Task 88 cost
    wiring) can record the routing decision without re-deciding.
    """
    if not config.MODEL_ROUTING_ENFORCED:
        name = provider_override or get_default_provider_name()
        decision = ModelRouteDecision(
            workflow_type=workflow_type,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            selected_provider=name,
            selected_model=_model_for(name),
            reason="routing_enforcement_disabled_legacy_path",
            warnings=["model_routing_enforced_false"],
        )
        return get_provider_by_name(name), decision

    # No-key / test / local profile: when the global default provider is
    # the keyless mock provider and the caller did not request a specific
    # provider, honor it. Routing a reasoning workflow to a hosted
    # provider (DeepSeek/Kimi) here would fail with no API key, and the
    # local-first profile explicitly means "no real providers configured"
    # (see docs/architecture.md provider strategy). decide_route — the
    # pure policy used by the preview endpoint — is intentionally left
    # unchanged.
    if not provider_override and get_default_provider_name() == "mock":
        decision = ModelRouteDecision(
            workflow_type=workflow_type,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            selected_provider="mock",
            selected_model=_model_for("mock"),
            reason="global_default_provider_is_mock_no_real_providers",
        )
        return get_provider_by_name("mock"), decision

    request = ModelRoutePreviewRequest(
        workflow_type=workflow_type,
        source_type=source_type,
        source_id=source_id,
        estimated_context_tokens=estimated_context_tokens,
        risk_level=risk_level,
        override_provider=provider_override,
        allow_expensive_provider=allow_expensive_provider,
        expensive_approved=expensive_approved,
    )
    decision = decide_route(request, project_id=project_id)

    # Defense in depth. decide_route._finish already reroutes a blocked
    # expensive provider to NORMAL; never hand back an expensive
    # provider the policy did not allow.
    if _is_expensive(decision.selected_provider) and not _expensive_allowed(
        request
    ):
        raise RoutedProviderError(
            f"Expensive provider {decision.selected_provider!r} blocked by "
            f"routing policy for workflow {workflow_type!r}"
        )

    return get_provider_by_name(decision.selected_provider), decision
