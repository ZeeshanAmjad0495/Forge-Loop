"""Small, shared route-layer helpers.

Used only where the S2 audit explicitly called out duplication: ~30
404-or-load sites and 8 provider-resolution sites. Sites with idiosyncratic
404 detail strings keep their inline form to preserve byte-identical
HTTP responses.
"""

from fastapi import HTTPException

from ..llm import ProviderError
from ..repositories_state import cost_record_repo
from ..services.model_routing import (
    RoutedProviderError,
    RiskLevel,
    WorkflowType,
    resolve_routed_provider,
)


def load_or_404(repo, object_id: str, label: str):
    obj = repo.get(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


def require_project(project_repo, project_id: str):
    return load_or_404(project_repo, project_id, "Project")


def resolve_routed_provider_or_400(
    workflow_type: "WorkflowType",
    provider_override: str | None = None,
    *,
    project_id: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    estimated_context_tokens: int = 0,
    risk_level: "RiskLevel" = "low",
    expensive_approved: bool = False,
):
    """Resolve an LLM provider through the enforced ModelRouter.

    Callers pass their workflow type and (optionally) the per-request
    provider override. Provider selection is the router's decision, not
    the caller's. Task 88: the routed call is BudgetGuard-checked and a
    ``planned``/``blocked`` CostRecord is persisted. ``expensive_approved``
    is the single per-request knob authorizing the expensive (Kimi)
    provider — it drives the route-decision expensive gate *and* the
    BudgetGuard approval. Returns ``(provider, decision)``.
    """
    try:
        return resolve_routed_provider(
            workflow_type,
            provider_override=provider_override,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            estimated_context_tokens=estimated_context_tokens,
            risk_level=risk_level,
            allow_expensive_provider=expensive_approved,
            expensive_approved=expensive_approved,
            approval_present=expensive_approved,
            cost_record_repo=cost_record_repo,
        )
    except RoutedProviderError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
