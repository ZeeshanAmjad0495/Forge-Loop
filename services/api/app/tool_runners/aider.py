"""C1: Aider coding-runner adapter.

ForgeLoop is a control plane — it delegates code execution to existing tools
rather than rebuilding them. This adapter conforms to the ``ToolRunner``
protocol exactly like ``OpenHandsRunner``: it is *pure* (builds an
instruction package + updates ToolRun records, no subprocess / network /
filesystem). External Aider execution is independently gated by
``AIDER_EXECUTION_ENABLED`` and is intentionally not implemented in this
build — a misroute can never shell out.

Aider reuses the ForgeLoop-configured LLM provider/key (e.g. DeepSeek); the
package records only the provider/model *names*, never the key.
"""

from __future__ import annotations

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
from .openhands import BASE_INSTRUCTIONS, _project_memory_summary

AIDER_INSTRUCTIONS: list[str] = [
    "You are running as Aider. Use Aider's edit/diff workflow.",
    "Make the smallest correct change; keep diffs reviewable.",
    "Do not run `aider --yes-always` style auto-commit; ForgeLoop owns commits.",
    "Do not create branches, open PRs, merge, or deploy.",
    "Return the proposed diff and a concise summary.",
]


def _llm_block() -> dict:
    """LLM identity for the Aider run — never an API key.

    Defaults to the local Ollama (project decision). For Ollama the local
    base_url + model are surfaced so a future execution path points Aider at
    the local server; other providers record provider/model only.
    """
    provider = config.AIDER_LLM_PROVIDER or config.LLM_PROVIDER
    if provider == "ollama":
        return {
            "provider": "ollama",
            "model": config.AIDER_MODEL or config.OLLAMA_DEFAULT_MODEL,
            "base_url": config.OLLAMA_BASE_URL,
        }
    return {
        "provider": provider,
        "model": config.AIDER_MODEL or config.LLM_MODEL or None,
    }


def build_aider_instruction_package(
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
    instructions = list(BASE_INSTRUCTIONS) + list(AIDER_INSTRUCTIONS)
    if safety_profile is not None:
        safety_block = {
            "work_safe_mode": safety_profile.work_safe_mode,
            "allowed_actions": list(safety_profile.allowed_actions or []),
            "blocked_paths": list(safety_profile.blocked_paths or []),
            "required_checks": list(safety_profile.required_checks or []),
            "requires_approval_for": list(
                safety_profile.requires_approval_for or []
            ),
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
                "work_safe_mode disabled — review carefully before running "
                "externally."
            )
    else:
        instructions.append(
            "No repo safety profile attached; assume strict defaults until "
            "one is configured."
        )

    return {
        "schema_version": "1",
        "runner": "aider",
        "mode": "dry_run",
        "llm": _llm_block(),
        "project": project_block,
        "repository": repo_block,
        "dev_task": dev_task_block,
        "context": context_block,
        "safety": safety_block,
        "instructions": instructions,
    }


class AiderRunner:
    """Aider coding-runner adapter — dry-run / instruction-package only.

    Execution is gated by ``config.AIDER_EXECUTION_ENABLED`` and is not
    implemented in this build; ``execute`` always raises so a misroute can
    never run a shell command.
    """

    runner_type: str = "aider"

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
        return build_aider_instruction_package(
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
        if not config.AIDER_EXECUTION_ENABLED:
            raise NotImplementedError("Aider execution is disabled")
        raise NotImplementedError(
            "Aider external execution is not implemented in this build"
        )
