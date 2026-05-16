from fastapi import APIRouter, Depends, HTTPException

from .. import config
from ..auth import require_auth
from ..repositories_state import cost_record_repo, project_repo
from ..services import provider_budget
from ..services.cost_tracking import record_cost
from ..services.model_routing import (
    ModelRouteDecision,
    ModelRoutePreviewRequest,
    decide_route,
    routing_summary,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/model-route/preview",
    response_model=ModelRouteDecision,
)
def preview_model_route(
    project_id: str,
    body: ModelRoutePreviewRequest,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    decision = decide_route(body, project_id=project_id)

    # Task 76: provider budget guard at the routing boundary. The expensive
    # provider is blocked when approval/budget is missing; the decision is
    # rerouted to the normal reasoning provider and the block is recorded.
    src_id = body.source_id or "model_route_preview"
    budget = provider_budget.check_provider_allowed(
        cost_record_repo,
        project_id=project_id,
        provider=decision.selected_provider,
        source_id=src_id,
        approval_present=bool(body.expensive_approved),
    )
    rec_status = "planned"
    if not budget.allowed:
        rec_status = "blocked"
        warnings = list(decision.warnings) + [
            f"budget_blocked:{budget.blocked_reason}"
        ]
        decision = decision.model_copy(update={
            "selected_provider": config.NORMAL_REASONING_PROVIDER,
            "selected_model": _model_for(config.NORMAL_REASONING_PROVIDER),
            "reason": f"{decision.reason}__budget_blocked",
            "expensive_provider_blocked": True,
            "warnings": warnings,
        })

    # Planned/blocked routing audit record (never raises).
    try:
        record_cost(
            cost_record_repo,
            project_id=project_id,
            source_type="model_route",
            source_id=src_id,
            workflow_type="manual",
            provider=decision.selected_provider,
            model=decision.selected_model,
            status=rec_status,
            selected_provider=decision.selected_provider,
            selected_model=decision.selected_model,
            routing_reason=decision.reason,
            fallback_chain=list(decision.fallback_chain),
            was_expensive_provider=(
                decision.selected_provider == config.EXPENSIVE_PROVIDER
            ),
            required_approval=decision.requires_human_approval,
            blocked_reason=(
                budget.blocked_reason if not budget.allowed else None
            ),
            metadata={
                "estimated_context_tokens": body.estimated_context_tokens,
                "risk_level": body.risk_level,
            },
        )
    except Exception:
        pass
    return decision


def _model_for(provider: str) -> str:
    from ..services.model_routing import _model_for as _mf

    return _mf(provider)


@router.get("/runtime/model-routing")
def get_model_routing(current_user: str = Depends(require_auth)):
    return routing_summary()
