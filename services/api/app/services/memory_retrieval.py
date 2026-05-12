"""Typed project memory retrieval policy (Release 9, Task 49).

Deterministic, low-cost retrieval over approved project memory candidates.
No embeddings, no vector DB, no semantic search — type + tag + recency.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..models import ProjectMemoryCandidate
from ..repositories import ProjectMemoryCandidateRepository

MemoryRetrievalPurpose = Literal[
    "requirement_analysis",
    "task_decomposition",
    "coding_instruction",
    "pr_review",
    "ci_analysis",
    "incident_analysis",
    "memory_learning",
    "research",
    "custom",
]


DEFAULT_POLICIES: dict[str, list[str]] = {
    "requirement_analysis": [
        "project_rule",
        "architecture_decision",
        "known_risk",
    ],
    "task_decomposition": [
        "project_rule",
        "architecture_decision",
        "coding_standard",
        "testing_rule",
    ],
    "coding_instruction": [
        "project_rule",
        "architecture_decision",
        "coding_standard",
        "testing_rule",
        "known_risk",
    ],
    "pr_review": [
        "coding_standard",
        "testing_rule",
        "known_failure_pattern",
        "known_risk",
    ],
    "ci_analysis": [
        "known_failure_pattern",
        "known_risk",
        "incident_learning",
    ],
    "incident_analysis": [
        "incident_learning",
        "known_failure_pattern",
        "known_risk",
    ],
    "memory_learning": [
        "approved_approach",
        "rejected_approach",
        "human_feedback",
    ],
    "research": [
        "approved_approach",
        "human_feedback",
    ],
    "custom": [],
}


class MemoryRetrievalRequest(BaseModel):
    purpose: MemoryRetrievalPurpose = "coding_instruction"
    memory_types: list[str] = []
    tags: list[str] = []
    source_types: list[str] = []
    max_items: int = 10
    include_approved_only: bool = True


class MemoryRetrievalItem(BaseModel):
    id: str
    memory_type: str
    title: str
    content: str
    tags: list[str]
    source_type: str
    source_id: str | None = None
    updated_at: str


class MemoryRetrievalResponse(BaseModel):
    items: list[MemoryRetrievalItem]
    policy_memory_types: list[str]
    total_matched: int


def _effective_memory_types(
    request: MemoryRetrievalRequest,
) -> list[str]:
    if request.memory_types:
        return list(request.memory_types)
    return list(DEFAULT_POLICIES.get(request.purpose, []))


def retrieve_memory(
    memory_candidate_repo: ProjectMemoryCandidateRepository,
    project_id: str,
    request: MemoryRetrievalRequest,
) -> MemoryRetrievalResponse:
    """Apply the typed policy and return the selected memory items."""
    types = _effective_memory_types(request)
    max_items = max(1, min(int(request.max_items or 10), 100))

    candidates: list[ProjectMemoryCandidate] = memory_candidate_repo.list_by_project(
        project_id
    )

    def _matches(c: ProjectMemoryCandidate) -> bool:
        if request.include_approved_only and c.status != "approved":
            return False
        if types and c.memory_type not in types:
            return False
        if request.tags and not (set(request.tags) & set(c.tags or [])):
            return False
        if request.source_types and c.source_type not in request.source_types:
            return False
        return True

    matched = [c for c in candidates if _matches(c)]
    matched.sort(key=lambda c: c.updated_at, reverse=True)
    selected = matched[:max_items]

    items = [
        MemoryRetrievalItem(
            id=c.id,
            memory_type=c.memory_type,
            title=c.title,
            content=c.content,
            tags=list(c.tags or []),
            source_type=c.source_type,
            source_id=c.source_id,
            updated_at=c.updated_at.isoformat(),
        )
        for c in selected
    ]
    return MemoryRetrievalResponse(
        items=items,
        policy_memory_types=types,
        total_matched=len(matched),
    )
