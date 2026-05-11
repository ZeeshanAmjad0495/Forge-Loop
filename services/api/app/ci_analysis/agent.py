import re
from typing import get_args

from ..llm.base import LLMProvider
from ..models import (
    CheckRun,
    CIAnalysisConclusion,
    CIEvent,
    DevTask,
    Project,
    ProjectContext,
    PullRequestDraft,
    Subtask,
)
from ..tool_runners.openhands import _project_memory_summary

_VALID_CONCLUSIONS: tuple[str, ...] = tuple(get_args(CIAnalysisConclusion))

_LOGS_EXCERPT_TRIM = 2000


def _truncate(value: str | None, limit: int) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def _linked_items_block(
    pr_draft: PullRequestDraft | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> str:
    lines: list[str] = []
    if pr_draft is not None:
        lines.append(f"- PR draft title: {pr_draft.title}")
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


def build_ci_failure_prompt(
    ci_event: CIEvent,
    project_context: ProjectContext | None,
    pr_draft: PullRequestDraft | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> str:
    memory_excerpt = _project_memory_summary(project_context) or "(none)"
    linked = _linked_items_block(pr_draft, dev_task, subtask, check_run)
    logs = _truncate(ci_event.logs_excerpt, _LOGS_EXCERPT_TRIM) or "(no logs provided)"
    failure_summary = ci_event.failure_summary or "(no failure summary provided)"

    return f"""\
You are a senior software delivery and QAOps diagnostic agent.

A CI run has been ingested into a human-supervised SDLC platform. You produce a
short diagnostic brief that helps a human triage the failure. A human must
review this brief before any remediation. You are not executing the fix.

Rules:
- Do NOT invent missing log details. Mark uncertainty clearly.
- Do NOT claim a fix has been applied.
- Do NOT recommend merge or deploy.
- Do NOT include secrets, tokens, credentials, or environment values.
- Keep the brief short and actionable.

Respond in markdown using exactly these sections in order:

# CI Failure Analysis

## 1. Failure Summary
## 2. Likely Root Causes
## 3. Failure Category
   (one of: flaky_test, code_regression, dependency_issue,
    configuration_issue, infrastructure_issue, unknown, needs_human_review)
## 4. Affected Areas
## 5. Suggested Debugging Steps
## 6. Suggested ForgeLoop Follow-up Action
## 7. Human Review Required
   (yes or no, with one-line reason)

CI event:
- provider: {ci_event.provider}
- workflow: {ci_event.workflow_name or "(unknown)"}
- job: {ci_event.job_name or "(unknown)"}
- branch: {ci_event.branch or "(unknown)"}
- commit: {ci_event.commit_sha or "(unknown)"}
- status: {ci_event.status}
- conclusion: {ci_event.conclusion}
- failure_summary: {failure_summary}
- logs_excerpt:
{logs}

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


def _human_review_required(body: str) -> bool:
    line = _first_nonempty_line(body).lower()
    return line.startswith("yes")


def parse_ci_failure_response(raw_text: str) -> dict:
    """Parse the structured markdown response into CIAnalysis fields.

    Falls back to a single-section ``summary`` with ``conclusion='unknown'`` if
    the structured sections aren't found. Never raises on unexpected content.
    """
    sections = _split_sections(raw_text or "")

    def _by_keyword(keyword: str) -> str:
        for title, body in sections.items():
            if keyword in title:
                return body
        return ""

    summary_body = _by_keyword("failure summary")
    causes_body = _by_keyword("root cause")
    category_body = _by_keyword("failure category")
    areas_body = _by_keyword("affected area")
    steps_body = _by_keyword("debugging step") or _by_keyword("suggested")
    follow_up_body = _by_keyword("follow-up") or _by_keyword("follow up")
    review_body = _by_keyword("human review")

    if not sections:
        return {
            "summary": (raw_text or "").strip()[:1000],
            "likely_root_causes": [],
            "suggested_fixes": [],
            "affected_areas": [],
            "recommended_next_action": None,
            "conclusion": "unknown",
        }

    conclusion = _match_conclusion(category_body) or "unknown"
    if review_body and _human_review_required(review_body):
        if conclusion == "unknown":
            conclusion = "needs_human_review"

    return {
        "summary": summary_body.strip(),
        "likely_root_causes": _bulletize(causes_body),
        "suggested_fixes": _bulletize(steps_body),
        "affected_areas": _bulletize(areas_body),
        "recommended_next_action": _first_nonempty_line(follow_up_body) or None,
        "conclusion": conclusion,
    }


def run_ci_failure_analysis(
    ci_event: CIEvent,
    provider: LLMProvider,
    project_context: ProjectContext | None,
    pr_draft: PullRequestDraft | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    check_run: CheckRun | None,
) -> dict:
    """Build the prompt, call the LLM, return parsed fields + raw_output.

    Raises whatever the provider raises; the caller persists a failed analysis.
    """
    prompt = build_ci_failure_prompt(
        ci_event=ci_event,
        project_context=project_context,
        pr_draft=pr_draft,
        dev_task=dev_task,
        subtask=subtask,
        check_run=check_run,
    )
    raw_output = provider.generate_text(prompt)
    parsed = parse_ci_failure_response(raw_output)
    parsed["raw_output"] = raw_output
    return parsed
