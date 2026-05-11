from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Artifact(BaseModel):
    id: str
    ticket_id: str | None = None
    requirement_id: str | None = None
    agent_run_id: str | None = None
    artifact_type: Literal[
        "implementation_brief",
        "requirement_analysis",
        "task_decomposition",
        "requirement_generation",
        "check_result",
        "tool_run_result",
        "openhands_instruction_package",
        "pr_review",
        "ci_failure_analysis",
        "incident_analysis",
        "memory_learning_summary",
        "memory_candidate_batch",
        "command_run_output",
        "openhands_execution_output",
        "openhands_execution_changed_paths",
        "git_inspection_summary",
        "git_commit_summary",
    ]
    content: str
    created_at: datetime
