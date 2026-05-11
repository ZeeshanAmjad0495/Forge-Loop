import re
from typing import get_args

from ..llm.base import LLMProvider
from ..models import (
    CheckRun,
    CIAnalysis,
    CIEvent,
    DevTask,
    Incident,
    IncidentAnalysisConclusion,
    ProjectContext,
    PullRequestDraft,
    PullRequestReview,
    Subtask,
)
from ..tool_runners.openhands import _project_memory_summary

_VALID_CONCLUSIONS: tuple[str, ...] = tuple(get_args(IncidentAnalysisConclusion))

_EVIDENCE_TRIM = 2000


def _truncate(value: str | None, limit: int) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def _linked_items_block(
    ci_event: CIEvent | None,
    ci_analysis: CIAnalysis | None,
    pr_draft: PullRequestDraft | None,
    pr_review: PullRequestReview | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> str:
    lines: list[str] = []
    if ci_event is not None:
        lines.append(
            f"- CI event: provider={ci_event.provider} workflow={ci_event.workflow_name or '(unknown)'}"
            f" conclusion={ci_event.conclusion}"
        )
    if ci_analysis is not None:
        lines.append(
            f"- CI analysis: conclusion={ci_analysis.conclusion}"
            + (f" summary={ci_analysis.summary[:200]}" if ci_analysis.summary else "")
        )
    if pr_draft is not None:
        lines.append(f"- PR draft title: {pr_draft.title}")
    if pr_review is not None:
        lines.append(
            f"- PR review: status={pr_review.status} conclusion={pr_review.conclusion}"
        )
    if dev_task is not None:
        lines.append(f"- Dev task title: {dev_task.title} (type: {dev_task.task_type})")
    if subtask is not None:
        lines.append(f"- Subtask title: {subtask.title}")
    if check_run is not None:
        lines.append(
            f"- Check run: {check_run.target_type}/{check_run.target_id}"
            f" conclusion={check_run.conclusion}"
            + (f" summary={check_run.summary}" if check_run.summary else "")
        )
    if not lines:
        return "- (none)"
    return "\n".join(lines)


def build_incident_triage_prompt(
    incident: Incident,
    project_context: ProjectContext | None,
    ci_event: CIEvent | None,
    ci_analysis: CIAnalysis | None,
    pr_draft: PullRequestDraft | None,
    pr_review: PullRequestReview | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> str:
    memory_excerpt = _project_memory_summary(project_context) or "(none)"
    linked = _linked_items_block(
        ci_event, ci_analysis, pr_draft, pr_review, dev_task, subtask, check_run
    )
    evidence = _truncate(incident.evidence, _EVIDENCE_TRIM) or "(no evidence provided)"

    return f"""\
You are a senior incident triage and remediation diagnostic agent for a
human-supervised SDLC + STLC control plane.

A production / operational incident has been recorded into the platform. You
produce a short triage and remediation brief that helps a human triage the
incident. A human must review and approve every step before any remediation
or deployment. You are not executing any fix.

Rules:
- Do NOT invent missing logs, metrics, dashboards, or production state.
- Mark uncertainty explicitly.
- Do NOT claim production has been changed by ForgeLoop.
- Do NOT recommend direct deployment, hotfix-to-prod, merge, or rollback as
  an automated step. Humans approve all such actions.
- Do NOT include secrets, tokens, credentials, or customer PII.
- Keep the brief short, actionable, and reviewable.

Respond in markdown using exactly these sections in order:

# Incident Triage Brief

## 1. Incident Summary
## 2. Impact Assessment
## 3. Likely Root Causes
## 4. Uncertainty / Missing Evidence
## 5. Immediate Safe Actions
## 6. Remediation Plan
## 7. Prevention Actions
## 8. Affected Areas
## 9. Suggested ForgeLoop Follow-up Work Item
## 10. Human Approval Points
## 11. Failure Category
   (one of: code_regression, configuration_issue, infrastructure_issue,
    dependency_issue, data_issue, security_issue, flaky_external_service,
    unknown, needs_human_review)

Incident:
- title: {incident.title}
- severity: {incident.severity}
- status: {incident.status}
- source: {incident.source}
- environment: {incident.environment or "(unknown)"}
- affected_area: {incident.affected_area or "(unknown)"}
- description: {incident.description}
- evidence:
{evidence}

Linked items (only those present are shown):
{linked}

Project memory (optional, may be empty):
{memory_excerpt}
"""


_SECTION_HEADING_RE = re.compile(
    r"^\s*##\s*\d+\.\s*(?P<title>[^\n]+?)\s*$",
    re.MULTILINE,
)


def _split_sections(text: str) -> dict[str, str]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return {}
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        title = m.group("title").strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections[title] = body
    return sections


def _bulletize(body: str) -> list[str]:
    items: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            items.append(line[2:].strip())
        elif re.match(r"^\d+[.)]\s+", line):
            items.append(re.sub(r"^\d+[.)]\s+", "", line).strip())
        else:
            items.append(line)
    return [i for i in items if i]


def _first_nonempty_line(body: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line:
            return line
    return ""


def _match_conclusion(body: str) -> str | None:
    lowered = body.lower()
    for candidate in _VALID_CONCLUSIONS:
        if candidate in lowered:
            return candidate
    return None


def parse_incident_triage_response(raw_text: str) -> dict:
    """Parse the structured markdown response into IncidentAnalysis fields.

    Falls back to a single-section ``summary`` with ``conclusion='unknown'`` if
    the structured sections aren't found. Never raises on unexpected content.
    """
    sections = _split_sections(raw_text or "")

    def _by_keyword(*keywords: str) -> str:
        for title, body in sections.items():
            for keyword in keywords:
                if keyword in title:
                    return body
        return ""

    summary_body = _by_keyword("incident summary", "summary")
    impact_body = _by_keyword("impact")
    causes_body = _by_keyword("root cause")
    immediate_body = _by_keyword("immediate", "safe action")
    remediation_body = _by_keyword("remediation")
    prevention_body = _by_keyword("prevention")
    areas_body = _by_keyword("affected area")
    follow_up_body = _by_keyword("follow-up", "follow up", "work item")
    category_body = _by_keyword("failure category", "category")

    if not sections:
        return {
            "summary": (raw_text or "").strip()[:1000],
            "impact_assessment": None,
            "likely_root_causes": [],
            "immediate_actions": [],
            "remediation_plan": [],
            "prevention_actions": [],
            "affected_areas": [],
            "recommended_next_action": None,
            "conclusion": "unknown",
        }

    conclusion = _match_conclusion(category_body) or "unknown"

    return {
        "summary": summary_body.strip(),
        "impact_assessment": impact_body.strip() or None,
        "likely_root_causes": _bulletize(causes_body),
        "immediate_actions": _bulletize(immediate_body),
        "remediation_plan": _bulletize(remediation_body),
        "prevention_actions": _bulletize(prevention_body),
        "affected_areas": _bulletize(areas_body),
        "recommended_next_action": _first_nonempty_line(follow_up_body) or None,
        "conclusion": conclusion,
    }


def run_incident_triage(
    incident: Incident,
    provider: LLMProvider,
    project_context: ProjectContext | None,
    ci_event: CIEvent | None,
    ci_analysis: CIAnalysis | None,
    pr_draft: PullRequestDraft | None,
    pr_review: PullRequestReview | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> dict:
    """Build the prompt, call the LLM, return parsed fields + raw_output.

    Raises whatever the provider raises; the caller persists a failed analysis.
    """
    prompt = build_incident_triage_prompt(
        incident=incident,
        project_context=project_context,
        ci_event=ci_event,
        ci_analysis=ci_analysis,
        pr_draft=pr_draft,
        pr_review=pr_review,
        dev_task=dev_task,
        subtask=subtask,
        check_run=check_run,
    )
    raw_output = provider.generate_text(prompt)
    parsed = parse_incident_triage_response(raw_output)
    parsed["raw_output"] = raw_output
    return parsed
