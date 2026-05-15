from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ArtifactStorageProvider = Literal["database", "filesystem"]


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
        "integration_run_summary",
        "aider_instruction_package",
        "github_pr_creation_summary",
        "review_feedback_import_summary",
        "revision_plan_summary",
        "review_feedback_resolution_summary",
        "research_brief",
        "architecture_review",
        "project_retrospective",
        "backup_export",
    ]
    content: str
    created_at: datetime

    # --- Release 8 Task 43: optional storage metadata (backward compatible) ---
    storage_provider: ArtifactStorageProvider = "database"
    storage_path: str | None = None
    content_size_bytes: int | None = None
    content_sha256: str | None = None
