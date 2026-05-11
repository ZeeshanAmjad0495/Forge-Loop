"""Approve a memory candidate into durable project memory (Task 32).

Maps each ``MemoryCandidateMemoryType`` to a target free-form field on
``ProjectContext`` and appends a deterministic block marked with the candidate
id. Re-applying the same candidate is a no-op (idempotent on the marker).

Pure helper — no IO. Caller persists the returned context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import ProjectContext, ProjectMemoryCandidate

# Mapping of memory_type → target ProjectContext field. Only the four fields
# already surfaced by the openhands prompt summariser are used as durable
# memory targets so approved learnings flow into existing prompts.
MEMORY_TYPE_TO_FIELD: dict[str, str] = {
    "architecture_decision": "architecture_notes",
    "important_file":        "architecture_notes",
    "prompt_note":           "architecture_notes",
    "cost_note":             "architecture_notes",
    "custom":                "architecture_notes",

    "project_rule":          "domain_rules",
    "approved_approach":     "domain_rules",
    "rejected_approach":     "domain_rules",
    "human_feedback":        "domain_rules",

    "coding_standard":       "coding_standards",
    "testing_rule":          "coding_standards",
    "deployment_rule":       "coding_standards",

    "known_risk":            "safety_rules",
    "known_failure_pattern": "safety_rules",
    "qa_learning":           "safety_rules",
    "incident_learning":     "safety_rules",
}


def target_field_for(memory_type: str) -> str:
    """Return which ``ProjectContext`` field a memory_type maps to."""
    return MEMORY_TYPE_TO_FIELD.get(memory_type, "architecture_notes")


def _marker(candidate_id: str) -> str:
    return f"[memory:{candidate_id}]"


def _build_block(candidate: ProjectMemoryCandidate) -> str:
    tag_line = ""
    if candidate.tags:
        tag_line = "\ntags: " + ", ".join(candidate.tags)
    return (
        f"{_marker(candidate.id)} {candidate.memory_type} — {candidate.title}\n"
        f"{candidate.content.strip()}"
        f"{tag_line}"
    )


def _empty_context(project_id: str) -> ProjectContext:
    return ProjectContext(
        project_id=project_id,
        architecture_notes="",
        coding_standards="",
        test_commands="",
        deployment_commands="",
        domain_rules="",
        safety_rules="",
        updated_at=None,
    )


def apply_candidate(
    context: ProjectContext | None,
    candidate: ProjectMemoryCandidate,
) -> ProjectContext:
    """Return a new ProjectContext with the candidate appended.

    If a block with the same candidate marker already exists in the target
    field, the context is returned unchanged (idempotent). The caller persists
    the returned object.
    """
    ctx = context or _empty_context(candidate.project_id)
    field = target_field_for(candidate.memory_type)
    current = getattr(ctx, field) or ""

    if _marker(candidate.id) in current:
        return ctx

    block = _build_block(candidate)
    new_value = (current.rstrip() + "\n\n" + block).lstrip() if current.strip() else block
    setattr(ctx, field, new_value)
    ctx.updated_at = datetime.now(timezone.utc)
    return ctx
