"""Architecture Review Agent service (Release 11, Task 65).

Stores architecture review briefs for ForgeLoop projects and ForgeLoop
itself, and can optionally generate a structured review from caller-provided
context via an injected LLM provider. The service does NOT modify code,
open PRs, or schedule background work. Tests must inject a mock provider —
no real network/LLM calls are made here.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ..llm.base import LLMProvider
from ..models import (
    ArchitectureReview,
    ArchitectureReviewCreate,
    ArchitectureReviewGenerateRequest,
    ArchitectureReviewUpdate,
    Artifact,
)
from ..repositories import (
    ArchitectureReviewRepository,
    ArtifactRepository,
)

_AGENT_SENTINEL = "ARCHITECTURE_REVIEW_AGENT"


def create_review(
    repo: ArchitectureReviewRepository,
    *,
    body: ArchitectureReviewCreate,
) -> ArchitectureReview:
    now = datetime.now(timezone.utc)
    completed_at = now if body.status == "completed" else None
    review = ArchitectureReview(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        target_type=body.target_type,
        target_id=body.target_id,
        title=body.title,
        scope=body.scope,
        status=body.status,
        summary=body.summary,
        findings=list(body.findings),
        recommendations=list(body.recommendations),
        risks=list(body.risks),
        score=body.score,
        provider=body.provider,
        model=body.model,
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )
    repo.save(review)
    return review


def update_review(
    repo: ArchitectureReviewRepository,
    review: ArchitectureReview,
    body: ArchitectureReviewUpdate,
) -> ArchitectureReview:
    data = review.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    now = datetime.now(timezone.utc)
    new_status = data.get("status")
    if new_status == "completed" and not data.get("completed_at"):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = ArchitectureReview(**data)
    repo.update(updated)
    return updated


def archive_review(
    repo: ArchitectureReviewRepository, review: ArchitectureReview
) -> ArchitectureReview:
    return update_review(repo, review, ArchitectureReviewUpdate(status="archived"))


def _build_prompt(body: ArchitectureReviewGenerateRequest) -> str:
    return f"""\
{_AGENT_SENTINEL}

You are a careful software architecture reviewer inside a human-supervised
SDLC platform called ForgeLoop. Review the supplied context and produce a
structured architecture review brief.

Examine, at minimum:
- architecture complexity
- local-first / cloud-optional boundaries
- repository abstractions
- security / work-safe behavior
- cost / context / model routing
- quality / evaluation signals
- maintainability risks
- scope creep risks

Rules:
- Do NOT propose direct code edits.
- Do NOT propose PRs or new runners.
- Do NOT invent facts not present in the provided context.
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text):

{{
  "summary": "one-paragraph summary",
  "findings": ["finding 1", "finding 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "risks": ["risk 1", "risk 2"],
  "score": null
}}

Title: {body.title}
Target type: {body.target_type}
Target id: {body.target_id or "none"}
Scope: {body.scope or "none"}

Context:
{body.context or "none"}
"""


def _parse_review(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _coerce_score(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_review(
    repo: ArchitectureReviewRepository,
    artifact_repo: ArtifactRepository,
    provider: LLMProvider,
    *,
    body: ArchitectureReviewGenerateRequest,
) -> tuple[ArchitectureReview, Artifact]:
    now = datetime.now(timezone.utc)
    review_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    prompt = _build_prompt(body)
    try:
        raw = provider.generate_text(prompt)
    except Exception as exc:  # pragma: no cover - exercised via failing provider
        review = ArchitectureReview(
            id=review_id,
            project_id=body.project_id,
            target_type=body.target_type,
            target_id=body.target_id,
            title=body.title,
            scope=body.scope,
            status="failed",
            provider=provider.provider_name,
            model=provider.model_name,
            created_at=now,
            updated_at=now,
            error_message=str(exc),
        )
        repo.save(review)
        return review, Artifact(
            id=artifact_id,
            artifact_type="architecture_review",
            content="",
            created_at=now,
        )

    parsed = _parse_review(raw)
    artifact = Artifact(
        id=artifact_id,
        artifact_type="architecture_review",
        content=raw,
        created_at=now,
    )

    review = ArchitectureReview(
        id=review_id,
        project_id=body.project_id,
        target_type=body.target_type,
        target_id=body.target_id,
        title=body.title,
        scope=body.scope,
        status="completed" if parsed else "failed",
        summary=parsed.get("summary") if parsed else None,
        findings=list(parsed.get("findings", [])) if parsed else [],
        recommendations=list(parsed.get("recommendations", [])) if parsed else [],
        risks=list(parsed.get("risks", [])) if parsed else [],
        score=_coerce_score(parsed.get("score")) if parsed else None,
        provider=provider.provider_name,
        model=provider.model_name,
        artifact_id=artifact.id,
        created_at=now,
        updated_at=now,
        completed_at=now if parsed else None,
        error_message=None if parsed else "Provider response could not be parsed.",
    )
    artifact_repo.save(artifact)
    repo.save(review)
    return review, artifact
