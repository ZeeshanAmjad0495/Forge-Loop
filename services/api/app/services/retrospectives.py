"""Post-project retrospective service (Release 11, Task 69).

Stores and (optionally) generates structured project retrospectives. The
service does NOT modify architecture, auto-create proposals, or schedule
follow-up work. Tests must inject a mock provider — no real LLM calls.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ..llm.base import LLMProvider
from ..models import (
    Artifact,
    ProjectRetrospective,
    ProjectRetrospectiveCreate,
    ProjectRetrospectiveGenerateRequest,
    ProjectRetrospectiveUpdate,
)
from ..repositories import (
    ArtifactRepository,
    ProjectRetrospectiveRepository,
)

_AGENT_SENTINEL = "PROJECT_RETROSPECTIVE_AGENT"


def create_retrospective(
    repo: ProjectRetrospectiveRepository,
    *,
    project_id: str,
    body: ProjectRetrospectiveCreate,
) -> ProjectRetrospective:
    now = datetime.now(timezone.utc)
    completed_at = now if body.status == "completed" else None
    retro = ProjectRetrospective(
        id=str(uuid.uuid4()),
        project_id=project_id,
        trial_id=body.trial_id,
        title=body.title,
        status=body.status,
        summary=body.summary,
        what_worked=list(body.what_worked),
        what_failed=list(body.what_failed),
        quality_notes=body.quality_notes,
        cost_notes=body.cost_notes,
        feedback_themes=list(body.feedback_themes),
        failure_themes=list(body.failure_themes),
        decisions=list(body.decisions),
        recommendations=list(body.recommendations),
        memory_candidate_ids=list(body.memory_candidate_ids),
        proposal_ids=list(body.proposal_ids),
        provider=body.provider,
        model=body.model,
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )
    repo.save(retro)
    return retro


def update_retrospective(
    repo: ProjectRetrospectiveRepository,
    retro: ProjectRetrospective,
    body: ProjectRetrospectiveUpdate,
) -> ProjectRetrospective:
    data = retro.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    now = datetime.now(timezone.utc)
    new_status = data.get("status")
    if new_status == "completed" and not data.get("completed_at"):
        data["completed_at"] = now
    data["updated_at"] = now
    updated = ProjectRetrospective(**data)
    repo.update(updated)
    return updated


def archive_retrospective(
    repo: ProjectRetrospectiveRepository,
    retro: ProjectRetrospective,
) -> ProjectRetrospective:
    return update_retrospective(
        repo, retro, ProjectRetrospectiveUpdate(status="archived")
    )


def _build_prompt(
    *,
    title: str,
    trial_id: str | None,
    summary_inputs: str,
) -> str:
    return f"""\
{_AGENT_SENTINEL}

You are writing a post-project retrospective inside a human-supervised SDLC
platform called ForgeLoop. Summarize the supplied inputs as a structured
retrospective.

Rules:
- Do NOT invent metrics not present in the supplied inputs.
- Do NOT propose direct code changes.
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text):

{{
  "summary": "one-paragraph summary",
  "what_worked": ["..."],
  "what_failed": ["..."],
  "quality_notes": "short notes or null",
  "cost_notes": "short notes or null",
  "feedback_themes": ["..."],
  "failure_themes": ["..."],
  "decisions": ["..."],
  "recommendations": ["..."]
}}

Title: {title}
Trial id: {trial_id or "none"}

Inputs:
{summary_inputs or "none"}
"""


def _parse_retro(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def generate_retrospective(
    repo: ProjectRetrospectiveRepository,
    artifact_repo: ArtifactRepository,
    provider: LLMProvider,
    *,
    project_id: str,
    trial_id: str | None,
    title: str,
    summary_inputs: str,
) -> tuple[ProjectRetrospective, Artifact]:
    now = datetime.now(timezone.utc)
    retro_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    prompt = _build_prompt(
        title=title,
        trial_id=trial_id,
        summary_inputs=summary_inputs,
    )
    try:
        raw = provider.generate_text(prompt)
    except Exception as exc:  # pragma: no cover - exercised via failing provider
        retro = ProjectRetrospective(
            id=retro_id,
            project_id=project_id,
            trial_id=trial_id,
            title=title,
            status="failed",
            provider=provider.provider_name,
            model=provider.model_name,
            created_at=now,
            updated_at=now,
            error_message=str(exc),
        )
        repo.save(retro)
        return retro, Artifact(
            id=artifact_id,
            artifact_type="project_retrospective",
            content="",
            created_at=now,
        )

    parsed = _parse_retro(raw)
    artifact = Artifact(
        id=artifact_id,
        artifact_type="project_retrospective",
        content=raw,
        created_at=now,
    )

    retro = ProjectRetrospective(
        id=retro_id,
        project_id=project_id,
        trial_id=trial_id,
        title=title,
        status="generated" if parsed else "failed",
        summary=parsed.get("summary") if parsed else None,
        what_worked=list(parsed.get("what_worked", [])) if parsed else [],
        what_failed=list(parsed.get("what_failed", [])) if parsed else [],
        quality_notes=parsed.get("quality_notes") if parsed else None,
        cost_notes=parsed.get("cost_notes") if parsed else None,
        feedback_themes=list(parsed.get("feedback_themes", [])) if parsed else [],
        failure_themes=list(parsed.get("failure_themes", [])) if parsed else [],
        decisions=list(parsed.get("decisions", [])) if parsed else [],
        recommendations=list(parsed.get("recommendations", [])) if parsed else [],
        provider=provider.provider_name,
        model=provider.model_name,
        artifact_id=artifact.id,
        created_at=now,
        updated_at=now,
        error_message=None if parsed else "Provider response could not be parsed.",
    )
    artifact_repo.save(artifact)
    repo.save(retro)
    return retro, artifact
