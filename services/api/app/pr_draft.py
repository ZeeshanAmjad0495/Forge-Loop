"""Deterministic PR-draft title/body generation (Task 28).

Pure functions only. No LLM, no I/O, no shell, no network.
"""
from .models import (
    CheckRun,
    CodeRepository,
    DevTask,
    Epic,
    Project,
    PullRequestDraft,
    RepoSafetyProfile,
    Requirement,
    Subtask,
    ToolRun,
)

_TITLE_LIMIT = 70
_TOOL_OUTPUT_LIMIT = 2000


def _truncate(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def derive_source_branch(dev_task: DevTask | None, subtask: Subtask | None) -> str:
    if dev_task is not None:
        return f"forgeloop/dev-task/{dev_task.id[:8]}"
    if subtask is not None:
        return f"forgeloop/subtask/{subtask.id[:8]}"
    return "forgeloop/draft"


def build_pr_draft_title(dev_task: DevTask | None, subtask: Subtask | None) -> str:
    if dev_task is not None:
        return _truncate(f"[ForgeLoop] {dev_task.title}", _TITLE_LIMIT)
    if subtask is not None:
        return _truncate(f"[ForgeLoop] {subtask.title}", _TITLE_LIMIT)
    return "[ForgeLoop] PR draft"


def build_pr_draft_body(
    *,
    project: Project,
    code_repository: CodeRepository,
    safety_profile: RepoSafetyProfile | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    requirement: Requirement | None,
    epic: Epic | None,
    tool_run: ToolRun | None,
    check_runs: list[CheckRun],
) -> str:
    lines: list[str] = []

    # Summary
    summary_text = ""
    if dev_task is not None and dev_task.description:
        summary_text = dev_task.description
    elif subtask is not None and subtask.description:
        summary_text = subtask.description
    lines.append("## Summary")
    lines.append(summary_text or "_No description provided._")
    lines.append("")

    # Linked items
    lines.append("## Linked ForgeLoop items")
    lines.append(f"- Project: {project.name}")
    lines.append(
        f"- Repository: {code_repository.name} ({code_repository.repo_url})"
    )
    if dev_task is not None:
        lines.append(f"- Dev task: {dev_task.id} — {dev_task.title}")
    if subtask is not None:
        lines.append(f"- Subtask: {subtask.id} — {subtask.title}")
    if requirement is not None:
        lines.append(f"- Requirement: {requirement.id} — {requirement.title}")
    if epic is not None:
        lines.append(f"- Epic: {epic.id} — {epic.title}")
    if tool_run is not None:
        lines.append(
            f"- Tool run: {tool_run.id} ({tool_run.runner_type}, "
            f"{tool_run.conclusion})"
        )
    lines.append("")

    # Implementation notes
    lines.append("## Implementation notes")
    if tool_run is not None:
        if tool_run.summary:
            lines.append(tool_run.summary)
        if tool_run.output:
            lines.append("")
            lines.append("```")
            lines.append(_truncate(tool_run.output, _TOOL_OUTPUT_LIMIT))
            lines.append("```")
    else:
        lines.append(
            "No ToolRun attached; record code changes manually before merging."
        )
    lines.append("")

    # Acceptance criteria / definition of done
    ac: list[str] = []
    dod: list[str] = []
    if dev_task is not None:
        ac = list(dev_task.acceptance_criteria or [])
        dod = list(dev_task.definition_of_done or [])
    elif subtask is not None:
        ac = list(subtask.acceptance_criteria or [])
    if ac:
        lines.append("## Acceptance criteria")
        for item in ac:
            lines.append(f"- [ ] {item}")
        lines.append("")
    if dod:
        lines.append("## Definition of done")
        for item in dod:
            lines.append(f"- [ ] {item}")
        lines.append("")

    # Tests / checks
    lines.append("## Tests / checks")
    if check_runs:
        all_success = all(r.conclusion == "success" for r in check_runs)
        for r in check_runs:
            label = r.conclusion or r.status
            lines.append(f"- [{label}] {r.summary or '(no summary)'}")
        if not all_success:
            lines.append("")
            lines.append(
                "⚠️ Not all checks succeeded. Do not claim tests passed."
            )
    else:
        lines.append(
            "⚠️ No deterministic check runs recorded against this task. "
            "Do not claim tests passed."
        )
    lines.append("")

    # QA evidence
    lines.append("## QA evidence")
    if check_runs:
        for r in check_runs:
            ref = r.artifact_id or r.id
            lines.append(f"- CheckRun {ref}: {r.summary or '(no summary)'}")
    else:
        lines.append("_No QA evidence recorded._")
    lines.append("")

    # Safety notes
    lines.append("## Safety notes")
    if safety_profile is not None:
        lines.append(f"- work_safe_mode: {safety_profile.work_safe_mode}")
        lines.append(
            "- Blocked paths honored: "
            + (", ".join(safety_profile.blocked_paths) or "_(none)_")
        )
        lines.append(
            "- Required checks: "
            + (", ".join(safety_profile.required_checks) or "_(none)_")
        )
        lines.append(
            "- Protected branches: "
            + (", ".join(safety_profile.protected_branches) or "_(none)_")
        )
    else:
        lines.append("⚠️ No repo safety profile configured.")
    lines.append("")

    # Approval checklist
    lines.append("## Human approval checklist")
    lines.append("- [ ] Code changes reviewed")
    lines.append("- [ ] Required checks passed")
    lines.append("- [ ] Secrets not committed")
    lines.append("- [ ] Blocked paths not modified")
    lines.append("- [ ] Protected branches not touched")
    lines.append("- [ ] Approved by human reviewer")
    lines.append("")

    # Known risks
    lines.append("## Known risks")
    lines.append(
        "- ForgeLoop did not execute any external coding tool or shell command."
    )
    lines.append(
        "- This PR draft is metadata only — no branch was created and no PR was opened."
    )
    lines.append("")

    lines.append("---")
    lines.append(
        "_Generated by ForgeLoop (PR-draft foundation). No GitHub API was called._"
    )

    return "\n".join(lines)


def build_pr_draft_content(
    *,
    project: Project,
    code_repository: CodeRepository,
    safety_profile: RepoSafetyProfile | None,
    dev_task: DevTask | None,
    subtask: Subtask | None,
    requirement: Requirement | None = None,
    epic: Epic | None = None,
    tool_run: ToolRun | None = None,
    check_runs: list[CheckRun] | None = None,
) -> tuple[str, str]:
    title = build_pr_draft_title(dev_task, subtask)
    body = build_pr_draft_body(
        project=project,
        code_repository=code_repository,
        safety_profile=safety_profile,
        dev_task=dev_task,
        subtask=subtask,
        requirement=requirement,
        epic=epic,
        tool_run=tool_run,
        check_runs=list(check_runs or []),
    )
    return title, body


_ALLOWED_PATCH_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft_prepared": {"awaiting_approval", "cancelled"},
    "awaiting_approval": {"cancelled"},
    "approved_for_creation": {"created", "failed", "cancelled"},
    "created": {"closed"},
    "failed": {"cancelled"},
    "closed": set(),
    "cancelled": set(),
}


def is_allowed_status_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in _ALLOWED_PATCH_STATUS_TRANSITIONS.get(current, set())
