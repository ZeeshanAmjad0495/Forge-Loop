from typing import Protocol

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


class ToolRunner(Protocol):
    """Minimal contract for coding tool runners.

    Runners are pure: they build instruction packages and update ToolRun records.
    They do not call subprocess, network, or filesystem I/O. Persistence is
    performed by route handlers.
    """

    runner_type: str

    def prepare_run(
        self,
        *,
        project: Project,
        dev_task: DevTask,
        code_repository: CodeRepository | None,
        safety_profile: RepoSafetyProfile | None,
        project_context: ProjectContext | None,
        definition: ToolRunnerDefinition | None,
    ) -> dict: ...

    def record_result(
        self,
        *,
        tool_run: ToolRun,
        summary: str,
        output: str,
        conclusion: ToolRunConclusion,
    ) -> ToolRun: ...
