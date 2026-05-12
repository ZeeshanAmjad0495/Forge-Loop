"""Artifact compression / summary service (Release 9, Task 50).

Produces deterministic, cheap summaries of artifact content so future
ContextPacks can prefer compact summaries over raw blobs.

Never calls real LLMs. Provider arg is recorded for traceability but does not
trigger an external call here — real LLM-driven summarization is gated by
later tasks (model routing / budget controls).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    Artifact,
    ArtifactSummary,
    ArtifactSummaryStatus,
    ArtifactSummaryType,
)
from ..repositories import ArtifactSummaryRepository
from .artifact_storage import read_artifact_content

_SHORT_LIMIT = 800
_AGENT_READY_LIMIT = 2000
_MAX_CONTENT_READ = 1_000_000  # 1 MB hard cap


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _project_id_for(artifact: Artifact) -> str | None:
    # Artifact does not currently carry project_id directly. Callers can
    # provide it explicitly; otherwise return None.
    return None


def _deterministic_summary(
    artifact: Artifact,
    *,
    content: str,
    summary_type: ArtifactSummaryType,
) -> dict:
    line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    byte_count = len(content.encode("utf-8"))
    short, short_truncated = _truncate(content, _SHORT_LIMIT)
    agent_ready, agent_truncated = _truncate(content, _AGENT_READY_LIMIT)

    structured: dict = {
        "artifact_type": artifact.artifact_type,
        "summary_type": summary_type,
        "line_count": line_count,
        "byte_count": byte_count,
        "short_truncated": short_truncated,
        "agent_ready_truncated": agent_truncated,
    }
    return {
        "short_summary": short,
        "structured_summary": structured,
        "agent_ready_summary": agent_ready,
    }


def summarize_artifact(
    artifact_summary_repo: ArtifactSummaryRepository,
    artifact: Artifact,
    *,
    summary_type: ArtifactSummaryType = "short",
    provider: str | None = None,
    model: str | None = None,
    project_id: str | None = None,
) -> ArtifactSummary:
    now = datetime.now(timezone.utc)
    status: ArtifactSummaryStatus = "completed"
    error_message: str | None = None

    try:
        raw = read_artifact_content(artifact)
    except Exception as exc:  # pragma: no cover - filesystem errors are environmental
        raw = ""
        status = "failed"
        error_message = str(exc)

    if len(raw) > _MAX_CONTENT_READ:
        raw = raw[:_MAX_CONTENT_READ]

    source_size = len(raw.encode("utf-8"))
    parts = _deterministic_summary(artifact, content=raw, summary_type=summary_type)
    summary_size = (
        len(parts["short_summary"].encode("utf-8"))
        + len(parts["agent_ready_summary"].encode("utf-8"))
    )
    compression_ratio = (
        round(summary_size / source_size, 4) if source_size > 0 else 0.0
    )

    summary = ArtifactSummary(
        id=str(uuid.uuid4()),
        project_id=project_id or _project_id_for(artifact),
        artifact_id=artifact.id,
        summary_type=summary_type,
        status=status,
        provider=provider or "fallback",
        model=model or "deterministic",
        short_summary=parts["short_summary"],
        structured_summary=parts["structured_summary"],
        agent_ready_summary=parts["agent_ready_summary"],
        source_size_bytes=source_size,
        summary_size_bytes=summary_size,
        compression_ratio=compression_ratio,
        error_message=error_message,
        metadata={},
        created_at=now,
        updated_at=now,
    )
    artifact_summary_repo.save(summary)
    return summary
