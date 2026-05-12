"""Model routing policy (Release 9, Task 51).

Selects providers/models for a given workflow without calling any provider.
Tasks 54–55 add Ollama / OpenAI-compatible providers; Task 53 adds budgets.
This module only makes the decision.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .. import config

WorkflowType = Literal[
    "analysis",
    "planning",
    "coding",
    "review",
    "qa",
    "ci",
    "incident",
    "memory",
    "compression",
    "research",
    "manual",
    "custom",
    "requirement_analysis",
    "task_decomposition",
    "implementation_planning",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
    "artifact_summary",
    "memory_extraction",
    "classification",
    "long_context_review",
    "high_risk",
    "test",
    "smoke",
    "demo",
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
    estimated_context_tokens: int = 0
    risk_level: RiskLevel = "low"
    requires_human_approval: bool = False
    warnings: list[str] = []


_LOCAL_WORKFLOWS = {
    "artifact_summary",
    "memory_extraction",
    "memory",
    "compression",
    "classification",
}

_REASONING_WORKFLOWS = {
    "analysis",
    "planning",
    "coding",
    "review",
    "ci",
    "incident",
    "qa",
    "research",
    "requirement_analysis",
    "task_decomposition",
    "implementation_planning",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
}

_TEST_WORKFLOWS = {"test", "smoke", "demo"}


def _long_context(estimated_tokens: int) -> bool:
    return estimated_tokens >= config.MODEL_ROUTING_LONG_CONTEXT_TOKENS


def _model_for(provider: str) -> str:
    if provider == "deepseek":
        return config.LLM_MODEL or "deepseek-chat"
    if provider == "kimi":
        return config.LLM_MODEL or "moonshot-v1-128k"
    if provider == "ollama":
        return config.OLLAMA_DEFAULT_MODEL
    if provider == "openai_compatible":
        return config.OPENAI_COMPATIBLE_MODEL or "gpt-4o-mini"
    if provider == config.OPENAI_COMPATIBLE_PROVIDER_NAME and config.OPENAI_COMPATIBLE_ENABLED:
        return config.OPENAI_COMPATIBLE_MODEL or "gpt-4o-mini"
    if provider == "mock":
        return "mock-1"
    return config.LLM_MODEL or "default"


def decide_route(
    request: ModelRoutePreviewRequest,
    project_id: str | None = None,
) -> ModelRouteDecision:
    warnings: list[str] = []

    if request.override_provider:
        return ModelRouteDecision(
            workflow_type=request.workflow_type,
            project_id=project_id,
            source_type=request.source_type,
            source_id=request.source_id,
            selected_provider=request.override_provider,
            selected_model=request.override_model or _model_for(request.override_provider),
            reason="explicit_override",
            estimated_context_tokens=request.estimated_context_tokens,
            risk_level=request.risk_level,
        )

    if not config.MODEL_ROUTING_ENABLED:
        provider = config.LLM_PROVIDER
        return ModelRouteDecision(
            workflow_type=request.workflow_type,
            project_id=project_id,
            source_type=request.source_type,
            source_id=request.source_id,
            selected_provider=provider,
            selected_model=_model_for(provider),
            reason="routing_disabled_use_global_llm_provider",
            estimated_context_tokens=request.estimated_context_tokens,
            risk_level=request.risk_level,
        )

    workflow = request.workflow_type
    long_ctx = _long_context(request.estimated_context_tokens)

    selected_provider: str
    fallback_provider: str | None = None
    reason: str
    requires_human_approval = False

    if workflow in _TEST_WORKFLOWS:
        selected_provider = config.TEST_PROVIDER
        reason = "test_smoke_demo_workflow"
    elif workflow in _LOCAL_WORKFLOWS:
        if config.OLLAMA_ENABLED:
            selected_provider = config.LOCAL_SUPPORT_PROVIDER
            fallback_provider = config.DEFAULT_REASONING_PROVIDER
            reason = "local_support_workflow_with_ollama"
        else:
            selected_provider = config.DEFAULT_REASONING_PROVIDER
            warnings.append("ollama_not_enabled_falling_back_to_reasoning_provider")
            reason = "local_support_workflow_no_ollama"
    elif workflow == "long_context_review" or long_ctx:
        selected_provider = config.LONG_CONTEXT_PROVIDER
        fallback_provider = config.DEFAULT_REASONING_PROVIDER
        reason = "long_context_threshold_exceeded" if long_ctx else "long_context_review_workflow"
    elif workflow == "high_risk" or request.risk_level == "high":
        selected_provider = config.LONG_CONTEXT_PROVIDER
        fallback_provider = config.DEFAULT_REASONING_PROVIDER
        requires_human_approval = True
        reason = "high_risk_workflow"
    elif workflow in _REASONING_WORKFLOWS:
        selected_provider = config.DEFAULT_REASONING_PROVIDER
        fallback_provider = config.LONG_CONTEXT_PROVIDER
        reason = "default_reasoning_workflow"
    else:
        selected_provider = config.DEFAULT_REASONING_PROVIDER
        fallback_provider = config.LONG_CONTEXT_PROVIDER
        reason = "default_unknown_workflow_uses_reasoning"
        warnings.append("unrecognized_workflow_type")

    selected_model = _model_for(selected_provider)
    fallback_model = _model_for(fallback_provider) if fallback_provider else None

    return ModelRouteDecision(
        workflow_type=workflow,
        project_id=project_id,
        source_type=request.source_type,
        source_id=request.source_id,
        selected_provider=selected_provider,
        selected_model=selected_model,
        reason=reason,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        estimated_context_tokens=request.estimated_context_tokens,
        risk_level=request.risk_level,
        requires_human_approval=requires_human_approval,
        warnings=warnings,
    )


def routing_summary() -> dict:
    """Return a snapshot of routing config for the runtime endpoint."""
    return {
        "enabled": config.MODEL_ROUTING_ENABLED,
        "default_reasoning_provider": config.DEFAULT_REASONING_PROVIDER,
        "long_context_provider": config.LONG_CONTEXT_PROVIDER,
        "local_support_provider": config.LOCAL_SUPPORT_PROVIDER,
        "test_provider": config.TEST_PROVIDER,
        "long_context_threshold_tokens": config.MODEL_ROUTING_LONG_CONTEXT_TOKENS,
        "ollama_enabled": config.OLLAMA_ENABLED,
        "openai_compatible_enabled": config.OPENAI_COMPATIBLE_ENABLED,
        "openai_compatible_provider_name": config.OPENAI_COMPATIBLE_PROVIDER_NAME,
    }
