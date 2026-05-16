"""Context pack assembly service (Release 9, Task 48).

ContextPack records what context was assembled for a model/agent/tool run.
This service stores summaries and references — not large raw file contents —
so packs stay cheap to read, query, and audit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import ContextPack, ContextPackPurpose
from ..repositories import ContextPackRepository


def estimate_tokens(text: str) -> int:
    """Cheap heuristic: ~1 token per 4 characters.

    Deliberately approximate. Avoids pulling in a tokenizer dependency.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def create_context_pack(
    context_pack_repo: ContextPackRepository,
    *,
    project_id: str,
    source_type: str,
    source_id: str,
    purpose: ContextPackPurpose,
    target_type: str | None = None,
    target_id: str | None = None,
    provider: str = "",
    model: str = "",
    content_summary: str = "",
    included_memory_ids: list[str] | None = None,
    included_artifact_ids: list[str] | None = None,
    included_requirement_ids: list[str] | None = None,
    included_task_ids: list[str] | None = None,
    included_file_refs: list[str] | None = None,
    rules_summary: str = "",
    safety_summary: str = "",
    estimated_tokens_value: int | None = None,
    actual_input_tokens: int = 0,
    artifact_id: str | None = None,
    metadata: dict | None = None,
    compression_level: str = "none",
    excluded_context_reasoning: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> ContextPack:
    if estimated_tokens_value is None:
        estimated_tokens_value = (
            estimate_tokens(content_summary)
            + estimate_tokens(rules_summary)
            + estimate_tokens(safety_summary)
        )

    now = datetime.now(timezone.utc)
    pack = ContextPack(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        purpose=purpose,
        provider=provider,
        model=model,
        content_summary=content_summary,
        included_memory_ids=list(included_memory_ids or []),
        included_artifact_ids=list(included_artifact_ids or []),
        included_requirement_ids=list(included_requirement_ids or []),
        included_task_ids=list(included_task_ids or []),
        included_file_refs=list(included_file_refs or []),
        rules_summary=rules_summary,
        safety_summary=safety_summary,
        estimated_tokens=max(0, int(estimated_tokens_value)),
        actual_input_tokens=max(0, int(actual_input_tokens)),
        artifact_id=artifact_id,
        metadata=dict(metadata or {}),
        compression_level=compression_level,  # type: ignore[arg-type]
        excluded_context_reasoning=list(excluded_context_reasoning or []),
        source_ids=list(source_ids or []),
        created_at=now,
        updated_at=now,
    )
    context_pack_repo.save(pack)
    return pack
