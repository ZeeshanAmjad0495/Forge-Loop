"""LLM-assisted memory learning agent (Task 32).

Distills a single source object's evidence block into 0–N durable memory
candidates. The agent is advisory only — humans approve every candidate
before it becomes durable project memory.
"""

from __future__ import annotations

import json
import re
from typing import Any, get_args

from ..llm.base import LLMProvider
from ..models import (
    MemoryCandidateMemoryType,
    ProjectContext,
)
from ..tool_runners.openhands import _project_memory_summary

_VALID_MEMORY_TYPES: tuple[str, ...] = tuple(get_args(MemoryCandidateMemoryType))


def build_memory_learning_prompt(
    project_context: ProjectContext | None,
    source_type: str,
    source_summary_block: str,
) -> str:
    memory_excerpt = _project_memory_summary(project_context) or "(none)"
    valid_types = ", ".join(_VALID_MEMORY_TYPES)

    return f"""\
Project Memory Learning

You are a senior project-memory distillation agent for a human-supervised
SDLC + STLC control plane (ForgeLoop). You are given evidence from one
finished work artifact (a CI analysis, incident analysis, PR review, check
run, tool run, approval, dev task, or subtask). Extract only durable,
reusable lessons that should be remembered for future work on this project.
Each candidate you propose will be reviewed by a human before becoming
durable project memory; nothing here writes anywhere automatically.

Hard rules:
- Output ONLY durable, reusable lessons. If the evidence has no durable
  lesson, return an empty Candidates block.
- Do not store raw logs, full stack traces, or transient error strings.
- Do not store secrets, tokens, credentials, environment values, or
  customer / PII data.
- Do not invent lessons not directly supported by the evidence.
- Mark uncertainty explicitly inside the content field.
- Prefer 1–5 small candidates over one large one.
- Each candidate must classify itself with a memory_type from this closed
  list: {valid_types}.
- Use tags as small free-form labels (no PII, no secrets).

Respond in markdown with exactly two sections in this order:

# Project Memory Learning

## Summary

(One short paragraph describing what was learned, or stating that nothing
durable was found.)

## Candidates

```json
[
  {{
    "memory_type": "<one of the closed list>",
    "title": "<short label>",
    "content": "<durable lesson, 1–4 sentences>",
    "tags": ["<tag>", "..."],
    "confidence": 0.0
  }}
]
```

If there are no durable lessons, return ``[]`` inside the json fence.

Source type: {source_type}

Source evidence:
{source_summary_block}

Project memory (optional, may be empty):
{memory_excerpt}
"""


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*(?P<body>\[.*?\])\s*```",
    re.DOTALL | re.IGNORECASE,
)
_SUMMARY_HEADING_RE = re.compile(
    r"^\s*##\s*Summary\s*$(?P<body>.*?)(?=^\s*##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _extract_summary(text: str) -> str:
    m = _SUMMARY_HEADING_RE.search(text or "")
    if not m:
        return ""
    return m.group("body").strip()


def _extract_candidate_json(text: str) -> list[dict]:
    if not text:
        return []
    m = _JSON_FENCE_RE.search(text)
    if not m:
        return []
    try:
        parsed = json.loads(m.group("body"))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(t).strip() for t in value if str(t).strip()]
    if isinstance(value, str) and value.strip():
        return [t.strip() for t in value.split(",") if t.strip()]
    return []


def _normalize_confidence(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result < 0.0:
        return 0.0
    if result > 1.0:
        return 1.0
    return result


def _normalize_candidate(item: dict) -> dict | None:
    """Coerce one raw LLM candidate into a clean dict, or drop it.

    Drops items missing required fields or whose ``memory_type`` is outside
    the closed Literal — keeps the system resilient to real-LLM variance
    without leaking unknown enum values into storage.
    """
    memory_type = (item.get("memory_type") or "").strip()
    title = (item.get("title") or "").strip()
    content = (item.get("content") or "").strip()
    if not memory_type or not title or not content:
        return None
    if memory_type not in _VALID_MEMORY_TYPES:
        return None
    return {
        "memory_type": memory_type,
        "title": title[:200],
        "content": content,
        "tags": _normalize_tags(item.get("tags")),
        "confidence": _normalize_confidence(item.get("confidence")),
    }


def parse_memory_learning_response(raw_text: str) -> tuple[str, list[dict]]:
    """Return ``(summary, candidates)`` parsed from the markdown response.

    Never raises on malformed input — returns ``(summary, [])`` if the
    candidates block is missing or invalid.
    """
    summary = _extract_summary(raw_text)
    raw_items = _extract_candidate_json(raw_text)
    candidates: list[dict] = []
    for item in raw_items:
        clean = _normalize_candidate(item)
        if clean is not None:
            candidates.append(clean)
    return summary, candidates


def run_memory_learning(
    provider: LLMProvider,
    project_context: ProjectContext | None,
    source_type: str,
    source_summary_block: str,
) -> dict:
    """Build the prompt, call the LLM, return parsed fields + raw_output.

    Raises whatever the provider raises; the caller persists a failed run.
    """
    prompt = build_memory_learning_prompt(
        project_context=project_context,
        source_type=source_type,
        source_summary_block=source_summary_block,
    )
    raw_output = provider.generate_text(prompt)
    summary, candidates = parse_memory_learning_response(raw_output)
    return {
        "summary": summary,
        "candidates": candidates,
        "raw_output": raw_output,
    }
