"""ResearchScout service (Release 11, Task 63).

Stores research briefs and optionally generates them from caller-provided
source summaries via an injected LLM provider. The service does NOT crawl
the web, fetch URLs, or schedule background research. Tests must inject a
mock provider — no real network/LLM calls are made here.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ..llm.base import LLMProvider
from ..models import (
    Artifact,
    ResearchBrief,
    ResearchBriefCreate,
    ResearchBriefGenerateRequest,
    ResearchBriefUpdate,
)
from ..repositories import (
    ArtifactRepository,
    ResearchBriefRepository,
)

_AGENT_SENTINEL = "RESEARCH_SCOUT_AGENT"


def create_brief(
    repo: ResearchBriefRepository,
    *,
    body: ResearchBriefCreate,
) -> ResearchBrief:
    now = datetime.now(timezone.utc)
    completed_at = now if body.status == "completed" else None
    brief = ResearchBrief(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        title=body.title,
        research_type=body.research_type,
        status=body.status,
        question=body.question,
        scope=body.scope,
        summary=body.summary,
        findings=list(body.findings),
        recommendations=list(body.recommendations),
        risks=list(body.risks),
        source_ids=list(body.source_ids),
        provider=body.provider,
        model=body.model,
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )
    repo.save(brief)
    return brief


def update_brief(
    repo: ResearchBriefRepository,
    brief: ResearchBrief,
    body: ResearchBriefUpdate,
) -> ResearchBrief:
    data = brief.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    now = datetime.now(timezone.utc)
    new_status = data.get("status")
    if new_status == "completed" and not data.get("completed_at"):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = ResearchBrief(**data)
    repo.update(updated)
    return updated


def archive_brief(
    repo: ResearchBriefRepository, brief: ResearchBrief
) -> ResearchBrief:
    return update_brief(repo, brief, ResearchBriefUpdate(status="archived"))


def _build_prompt(
    body: ResearchBriefGenerateRequest,
    source_summaries: list[str],
) -> str:
    sources_block = (
        "\n".join(f"- [{i + 1}] {s}" for i, s in enumerate(source_summaries))
        if source_summaries
        else "none"
    )
    return f"""\
{_AGENT_SENTINEL}

You are a careful research analyst inside a human-supervised SDLC platform
called ForgeLoop. Produce a research brief grounded ONLY in the provided
source summaries.

Rules:
- Do NOT invent or browse new sources.
- Do NOT hallucinate citations.
- If sources are insufficient, say so in `findings` and leave
  `recommendations` minimal / advisory.
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text):

{{
  "summary": "one-paragraph summary",
  "findings": ["finding 1", "finding 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "risks": ["risk 1", "risk 2"]
}}

Title: {body.title}
Research type: {body.research_type}
Question: {body.question or "none"}
Scope: {body.scope or "none"}

Provided source summaries (only these may be cited):
{sources_block}
"""


def _parse_brief(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def generate_brief(
    repo: ResearchBriefRepository,
    artifact_repo: ArtifactRepository,
    provider: LLMProvider,
    *,
    body: ResearchBriefGenerateRequest,
    source_summaries: list[str] | None = None,
) -> tuple[ResearchBrief, Artifact]:
    now = datetime.now(timezone.utc)
    summaries = source_summaries or []
    brief_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    prompt = _build_prompt(body, summaries)
    try:
        raw = provider.generate_text(prompt)
    except Exception as exc:  # pragma: no cover - exercised via failing provider
        brief = ResearchBrief(
            id=brief_id,
            project_id=body.project_id,
            title=body.title,
            research_type=body.research_type,
            status="failed",
            question=body.question,
            scope=body.scope,
            source_ids=list(body.source_ids),
            provider=provider.provider_name,
            model=provider.model_name,
            created_at=now,
            updated_at=now,
            error_message=str(exc),
        )
        repo.save(brief)
        return brief, Artifact(
            id=artifact_id,
            artifact_type="research_brief",
            content="",
            created_at=now,
        )

    parsed = _parse_brief(raw)

    artifact = Artifact(
        id=artifact_id,
        artifact_type="research_brief",
        content=raw,
        created_at=now,
    )

    brief = ResearchBrief(
        id=brief_id,
        project_id=body.project_id,
        title=body.title,
        research_type=body.research_type,
        status="completed" if parsed else "failed",
        question=body.question,
        scope=body.scope,
        summary=parsed.get("summary") if parsed else None,
        findings=list(parsed.get("findings", [])) if parsed else [],
        recommendations=list(parsed.get("recommendations", [])) if parsed else [],
        risks=list(parsed.get("risks", [])) if parsed else [],
        source_ids=list(body.source_ids),
        provider=provider.provider_name,
        model=provider.model_name,
        artifact_id=artifact.id,
        created_at=now,
        updated_at=now,
        completed_at=now if parsed else None,
        error_message=None if parsed else "Provider response could not be parsed.",
    )
    artifact_repo.save(artifact)
    repo.save(brief)
    return brief, artifact
