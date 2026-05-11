from datetime import datetime, timezone

from .. import config
from ..models import (
    CodeRepository,
    DevTask,
    Project,
    ProjectContext,
    RepoSafetyProfile,
    ToolRun,
    ToolRunConclusion,
    ToolRunnerDefinition,
)

BASE_INSTRUCTIONS: list[str] = [
    "Do not modify files matching any blocked path.",
    "Keep diffs small and reviewable.",
    "Add or update tests to cover changes.",
    "Do not commit secrets or credentials.",
    "Do not create branches.",
    "Do not open pull requests.",
    "Do not merge or deploy.",
    "Run required checks listed under safety.required_checks if execution mode supports it.",
    "Return the proposed diff and a summary; do not push.",
]

_MEMORY_TRIM = 1000


def _project_memory_summary(ctx: ProjectContext | None) -> str | None:
    if ctx is None:
        return None
    parts: list[str] = []
    for label, value in (
        ("architecture_notes", ctx.architecture_notes),
        ("safety_rules", ctx.safety_rules),
        ("coding_standards", ctx.coding_standards),
        ("domain_rules", ctx.domain_rules),
    ):
        if value:
            parts.append(f"{label}: {value}")
    if not parts:
        return None
    summary = "\n\n".join(parts)
    if len(summary) > _MEMORY_TRIM:
        summary = summary[:_MEMORY_TRIM] + "…"
    return summary


def build_openhands_instruction_package(
    *,
    project: Project,
    dev_task: DevTask,
    code_repository: CodeRepository | None,
    safety_profile: RepoSafetyProfile | None,
    project_context: ProjectContext | None,
    requirement_summary: str | None = None,
    epic_title: str | None = None,
) -> dict:
    project_block = {
        "id": project.id,
        "name": project.name,
        "tech_stack": list(project.tech_stack or []),
    }

    repo_block: dict | None = None
    if code_repository is not None:
        repo_block = {
            "id": code_repository.id,
            "repo_url": code_repository.repo_url,
            "default_branch": code_repository.default_branch,
            "provider": code_repository.provider,
        }

    dev_task_block = {
        "id": dev_task.id,
        "title": dev_task.title,
        "description": dev_task.description,
        "task_type": dev_task.task_type,
        "acceptance_criteria": list(dev_task.acceptance_criteria or []),
        "definition_of_done": list(dev_task.definition_of_done or []),
        "requirement_id": dev_task.requirement_id,
        "epic_id": dev_task.epic_id,
    }

    context_block = {
        "requirement_summary": requirement_summary,
        "epic_title": epic_title,
        "project_memory_summary": _project_memory_summary(project_context),
    }

    safety_block: dict | None = None
    instructions = list(BASE_INSTRUCTIONS)
    if safety_profile is not None:
        safety_block = {
            "work_safe_mode": safety_profile.work_safe_mode,
            "allowed_actions": list(safety_profile.allowed_actions or []),
            "blocked_paths": list(safety_profile.blocked_paths or []),
            "required_checks": list(safety_profile.required_checks or []),
            "requires_approval_for": list(safety_profile.requires_approval_for or []),
            "protected_branches": list(safety_profile.protected_branches or []),
        }
        if safety_profile.protected_branches:
            instructions.append(
                "Do not push to or modify protected branches: "
                + ", ".join(safety_profile.protected_branches)
                + "."
            )
        if not safety_profile.work_safe_mode:
            instructions.append(
                "work_safe_mode disabled — review carefully before running externally."
            )
    else:
        instructions.append(
            "No repo safety profile attached; assume strict defaults until one is configured."
        )

    return {
        "schema_version": "1",
        "runner": "openhands",
        "mode": "dry_run",
        "project": project_block,
        "repository": repo_block,
        "dev_task": dev_task_block,
        "context": context_block,
        "safety": safety_block,
        "instructions": instructions,
    }


class OpenHandsRunner:
    """OpenHands coding-runner adapter — dry-run / instruction-package mode only.

    Actual execution is gated by config.OPENHANDS_EXECUTION_ENABLED and is not
    implemented in this task. Even when invoked the execute path raises
    NotImplementedError so a misroute can never run a shell command.
    """

    runner_type: str = "openhands"

    def prepare_run(
        self,
        *,
        project: Project,
        dev_task: DevTask,
        code_repository: CodeRepository | None,
        safety_profile: RepoSafetyProfile | None,
        project_context: ProjectContext | None,
        definition: ToolRunnerDefinition | None,
        requirement_summary: str | None = None,
        epic_title: str | None = None,
    ) -> dict:
        return build_openhands_instruction_package(
            project=project,
            dev_task=dev_task,
            code_repository=code_repository,
            safety_profile=safety_profile,
            project_context=project_context,
            requirement_summary=requirement_summary,
            epic_title=epic_title,
        )

    def record_result(
        self,
        *,
        tool_run: ToolRun,
        summary: str,
        output: str,
        conclusion: ToolRunConclusion,
    ) -> ToolRun:
        now = datetime.now(timezone.utc)
        return tool_run.model_copy(
            update={
                "summary": summary,
                "output": output,
                "conclusion": conclusion,
                "completed_at": tool_run.completed_at or now,
                "updated_at": now,
            }
        )

    def execute(self, *args, **kwargs):
        if not config.OPENHANDS_EXECUTION_ENABLED:
            raise NotImplementedError("OpenHands execution is disabled")
        raise NotImplementedError(
            "OpenHands external execution is not implemented in this build"
        )
