"""Source fetching for memory learning runs (Task 32).

Centralises how `(source_type, source_id)` resolves to a concrete source object
plus a short prompt-friendly summary block. Keeps route handlers thin and
makes prompt content easy to assert in tests.
"""

from __future__ import annotations

from typing import Any

from ..models import (
    Approval,
    CIAnalysis,
    CheckRun,
    DevTask,
    IncidentAnalysis,
    PullRequestReview,
    Subtask,
    ToolRun,
)

# Sources actually implemented as learning-run inputs in this task.
# `manual` candidates skip the learning-run path entirely.
SUPPORTED_SOURCE_TYPES: tuple[str, ...] = (
    "ci_analysis",
    "incident_analysis",
    "pr_review",
    "check_run",
    "tool_run",
    "approval",
    "dev_task",
    "subtask",
)

_OUTPUT_TRIM = 1000


def _truncate(value: str | None, limit: int = _OUTPUT_TRIM) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def _bullets(items: list[str], limit: int = 5) -> str:
    if not items:
        return "  (none)"
    head = items[:limit]
    extra = len(items) - len(head)
    lines = [f"  - {item}" for item in head]
    if extra > 0:
        lines.append(f"  - (+{extra} more)")
    return "\n".join(lines)


def _ci_analysis_block(a: CIAnalysis) -> str:
    return (
        f"- conclusion: {a.conclusion}\n"
        f"- summary: {a.summary or '(none)'}\n"
        f"- likely root causes:\n{_bullets(a.likely_root_causes)}\n"
        f"- suggested fixes:\n{_bullets(a.suggested_fixes)}\n"
        f"- recommended next action: {a.recommended_next_action or '(none)'}"
    )


def _incident_analysis_block(a: IncidentAnalysis) -> str:
    return (
        f"- conclusion: {a.conclusion}\n"
        f"- summary: {a.summary or '(none)'}\n"
        f"- impact: {a.impact_assessment or '(none)'}\n"
        f"- likely root causes:\n{_bullets(a.likely_root_causes)}\n"
        f"- immediate actions:\n{_bullets(a.immediate_actions)}\n"
        f"- remediation plan:\n{_bullets(a.remediation_plan)}\n"
        f"- prevention actions:\n{_bullets(a.prevention_actions)}\n"
        f"- recommended next action: {a.recommended_next_action or '(none)'}"
    )


def _pr_review_block(r: PullRequestReview) -> str:
    finding_lines: list[str] = []
    for f in r.findings[:5]:
        sev = f.severity or "unknown"
        cat = f.category or "general"
        finding_lines.append(f"  - [{sev}/{cat}] {f.message}")
    if not finding_lines:
        finding_lines = ["  (none)"]
    extra = max(0, len(r.findings) - 5)
    if extra:
        finding_lines.append(f"  - (+{extra} more)")
    return (
        f"- conclusion: {r.conclusion}\n"
        f"- summary: {r.summary or '(none)'}\n"
        f"- findings:\n" + "\n".join(finding_lines) + "\n"
        f"- recommendations: {r.recommendations or '(none)'}"
    )


def _check_run_block(c: CheckRun) -> str:
    return (
        f"- target: {c.target_type}/{c.target_id}\n"
        f"- conclusion: {c.conclusion}\n"
        f"- summary: {c.summary or '(none)'}\n"
        f"- output (truncated):\n{_truncate(c.output)}"
    )


def _tool_run_block(t: ToolRun) -> str:
    return (
        f"- runner: {t.runner_type} mode={t.mode}\n"
        f"- target: {t.target_type}/{t.target_id}\n"
        f"- conclusion: {t.conclusion}\n"
        f"- summary: {t.summary or '(none)'}\n"
        f"- output (truncated):\n{_truncate(t.output)}"
    )


def _approval_block(a: Approval) -> str:
    return (
        f"- target: {a.target_type}/{a.target_id}\n"
        f"- status: {a.status}\n"
        f"- feedback: {a.feedback or '(none)'}"
    )


def _dev_task_block(t: DevTask) -> str:
    return (
        f"- title: {t.title}\n"
        f"- type: {t.task_type}\n"
        f"- status: {t.status}\n"
        f"- description: {_truncate(t.description, 600)}\n"
        f"- acceptance criteria:\n{_bullets(t.acceptance_criteria)}"
    )


def _subtask_block(s: Subtask) -> str:
    return (
        f"- title: {s.title}\n"
        f"- status: {s.status}\n"
        f"- description: {_truncate(s.description, 600)}\n"
        f"- acceptance criteria:\n{_bullets(s.acceptance_criteria)}"
    )


def fetch_source(
    source_type: str,
    source_id: str,
    *,
    ci_analysis_repo,
    incident_analysis_repo,
    pr_review_repo,
    check_run_repo,
    tool_run_repo,
    approval_repo,
    dev_task_repo,
    subtask_repo,
) -> tuple[Any, str] | None:
    """Resolve a source object and render a prompt-friendly summary block.

    Returns ``None`` when the source does not exist. Raises ``ValueError`` for
    source types not implemented in this task; the route handler maps that to
    a 400 response.
    """
    if source_type == "ci_analysis":
        obj = ci_analysis_repo.get(source_id)
        return (obj, _ci_analysis_block(obj)) if obj else None
    if source_type == "incident_analysis":
        obj = incident_analysis_repo.get(source_id)
        return (obj, _incident_analysis_block(obj)) if obj else None
    if source_type == "pr_review":
        obj = pr_review_repo.get(source_id)
        return (obj, _pr_review_block(obj)) if obj else None
    if source_type == "check_run":
        obj = check_run_repo.get(source_id)
        return (obj, _check_run_block(obj)) if obj else None
    if source_type == "tool_run":
        obj = tool_run_repo.get(source_id)
        return (obj, _tool_run_block(obj)) if obj else None
    if source_type == "approval":
        obj = approval_repo.get(source_id)
        return (obj, _approval_block(obj)) if obj else None
    if source_type == "dev_task":
        obj = dev_task_repo.get(source_id)
        return (obj, _dev_task_block(obj)) if obj else None
    if source_type == "subtask":
        obj = subtask_repo.get(source_id)
        return (obj, _subtask_block(obj)) if obj else None
    raise ValueError(
        f"source_type {source_type!r} is not supported as a learning-run input"
    )
