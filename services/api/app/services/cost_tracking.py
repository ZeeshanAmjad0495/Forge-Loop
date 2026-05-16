"""Cost and token tracking foundation (Release 9, Task 47).

Provides a tiny helper for creating ``CostRecord`` entries from already-known
token / cost components. Pricing is supplied by the caller — this module never
calls external providers and never fetches live pricing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    CostRecord,
    CostRecordSourceType,
    CostRecordStatus,
    CostRecordWorkflowType,
)
from ..repositories import CostRecordRepository


def record_cost(
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    source_type: CostRecordSourceType,
    source_id: str,
    workflow_type: CostRecordWorkflowType,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    estimated_input_cost_usd: float = 0.0,
    estimated_output_cost_usd: float = 0.0,
    estimated_cached_input_cost_usd: float = 0.0,
    currency: str = "USD",
    metadata: dict | None = None,
    # Task 76 audit fields (optional; defaults preserve prior behavior).
    status: CostRecordStatus = "completed",
    selected_provider: str | None = None,
    selected_model: str | None = None,
    routing_reason: str | None = None,
    fallback_chain: list[str] | None = None,
    was_expensive_provider: bool = False,
    required_approval: bool = False,
    approval_id: str | None = None,
    blocked_reason: str | None = None,
    actual_input_tokens: int | None = None,
    actual_output_tokens: int | None = None,
    actual_cost_usd: float | None = None,
) -> CostRecord:
    """Persist a ``CostRecord`` and return it.

    Token and cost components are clamped at zero. Totals are computed here so
    callers cannot drift from the per-component values.
    """

    input_tokens = max(0, int(input_tokens))
    output_tokens = max(0, int(output_tokens))
    cached_input_tokens = max(0, int(cached_input_tokens))
    estimated_input_cost_usd = max(0.0, float(estimated_input_cost_usd))
    estimated_output_cost_usd = max(0.0, float(estimated_output_cost_usd))
    estimated_cached_input_cost_usd = max(0.0, float(estimated_cached_input_cost_usd))

    total_tokens = input_tokens + output_tokens + cached_input_tokens
    estimated_total_cost_usd = (
        estimated_input_cost_usd
        + estimated_output_cost_usd
        + estimated_cached_input_cost_usd
    )

    now = datetime.now(timezone.utc)
    record = CostRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        workflow_type=workflow_type,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_tokens=total_tokens,
        estimated_input_cost_usd=estimated_input_cost_usd,
        estimated_output_cost_usd=estimated_output_cost_usd,
        estimated_cached_input_cost_usd=estimated_cached_input_cost_usd,
        estimated_total_cost_usd=estimated_total_cost_usd,
        currency=currency,
        metadata=dict(metadata or {}),
        status=status,
        selected_provider=selected_provider or provider,
        selected_model=selected_model or model,
        routing_reason=routing_reason,
        fallback_chain=list(fallback_chain or []),
        was_expensive_provider=was_expensive_provider,
        required_approval=required_approval,
        approval_id=approval_id,
        blocked_reason=blocked_reason,
        actual_input_tokens=actual_input_tokens,
        actual_output_tokens=actual_output_tokens,
        actual_cost_usd=actual_cost_usd,
        created_at=now,
        updated_at=now,
        completed_at=(
            now if status in ("completed", "failed", "blocked") else None
        ),
    )
    cost_record_repo.save(record)

    # C2: mirror the cost record to the observability provider as an LLM
    # generation. No-op unless Langfuse is configured; never raises.
    try:
        from .observability import get_observability_provider

        get_observability_provider().record_generation(
            name=f"{workflow_type}:{source_type}",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=estimated_total_cost_usd,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            metadata=dict(metadata or {}),
        )
    except Exception:
        pass

    return record
