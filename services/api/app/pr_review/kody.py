"""Kody/Kodus PR review adapter foundation (Task 29).

Pure module. No subprocess, no urllib, no httpx, no GitHub calls. Builds a
deterministic review-request package from ForgeLoop state and records review
results as PullRequestReview field updates. External execution is gated by
`config.KODY_REVIEW_ENABLED` and intentionally not implemented in this build.
"""
from datetime import datetime, timezone

from .. import config
from ..models import (
    Approval,
    CheckRun,
    CodeRepository,
    DevTask,
    Epic,
    Project,
    PullRequestDraft,
    PullRequestReview,
    PullRequestReviewConclusion,
    PullRequestReviewFinding,
    RepoSafetyProfile,
    Requirement,
    Subtask,
    ToolRun,
)

REVIEW_FOCUS_AREAS: list[str] = [
    "correctness",
    "tests",
    "security",
    "maintainability",
    "performance",
    "scope control",
    "adherence to project rules",
    "blocked path violations",
    "missing QA evidence",
]


_ALLOWED_REVIEW_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "completed", "failed", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": {"cancelled"},
    "failed": {"cancelled", "pending"},
    "cancelled": set(),
}


def is_allowed_review_status_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in _ALLOWED_REVIEW_STATUS_TRANSITIONS.get(current, set())


def _dev_task_block(dev_task: DevTask | None) -> dict | None:
    if dev_task is None:
        return None
    return {"id": dev_task.id, "title": dev_task.title}


def _subtask_block(subtask: Subtask | None) -> dict | None:
    if subtask is None:
        return None
    return {"id": subtask.id, "title": subtask.title}


def _requirement_block(requirement: Requirement | None) -> dict | None:
    if requirement is None:
        return None
    return {"id": requirement.id, "title": requirement.title}


def _epic_block(epic: Epic | None) -> dict | None:
    if epic is None:
        return None
    return {"id": epic.id, "title": epic.title}


def _tool_run_block(tool_run: ToolRun | None) -> dict | None:
    if tool_run is None:
        return None
    return {
        "id": tool_run.id,
        "runner_type": tool_run.runner_type,
        "status": tool_run.status,
        "conclusion": tool_run.conclusion,
        "summary": tool_run.summary,
    }


def _qa_evidence_block(check_runs: list[CheckRun]) -> list[dict]:
    return [
        {
            "check_run_id": r.id,
            "status": r.status,
            "conclusion": r.conclusion,
            "summary": r.summary,
            "artifact_id": r.artifact_id,
        }
        for r in check_runs
    ]


def _safety_block(profile: RepoSafetyProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "work_safe_mode": profile.work_safe_mode,
        "allowed_actions": list(profile.allowed_actions or []),
        "blocked_paths": list(profile.blocked_paths or []),
        "required_checks": list(profile.required_checks or []),
        "requires_approval_for": list(profile.requires_approval_for or []),
        "protected_branches": list(profile.protected_branches or []),
    }


def _human_approval_block(approvals: list[Approval]) -> dict | None:
    if not approvals:
        return None
    latest = sorted(approvals, key=lambda a: a.created_at, reverse=True)[0]
    return {
        "status": latest.status,
        "decided_by": latest.decided_by,
        "feedback": latest.feedback,
    }


def build_kody_review_package(
    *,
    pr_draft: PullRequestDraft,
    project: Project,
    code_repository: CodeRepository,
    safety_profile: RepoSafetyProfile | None = None,
    dev_task: DevTask | None = None,
    subtask: Subtask | None = None,
    requirement: Requirement | None = None,
    epic: Epic | None = None,
    tool_run: ToolRun | None = None,
    check_runs: list[CheckRun] | None = None,
    approvals: list[Approval] | None = None,
) -> dict:
    return {
        "schema_version": "1",
        "provider": "kody",
        "mode": "prepare",
        "project": {
            "id": project.id,
            "name": project.name,
            "tech_stack": list(project.tech_stack or []),
        },
        "repository": {
            "id": code_repository.id,
            "repo_url": code_repository.repo_url,
            "default_branch": code_repository.default_branch,
            "provider": code_repository.provider,
        },
        "pr_draft": {
            "id": pr_draft.id,
            "title": pr_draft.title,
            "body": pr_draft.body,
            "source_branch": pr_draft.source_branch,
            "target_branch": pr_draft.target_branch,
            "status": pr_draft.status,
        },
        "linked": {
            "dev_task": _dev_task_block(dev_task),
            "subtask": _subtask_block(subtask),
            "requirement": _requirement_block(requirement),
            "epic": _epic_block(epic),
            "tool_run": _tool_run_block(tool_run),
        },
        "qa_evidence": _qa_evidence_block(list(check_runs or [])),
        "safety": _safety_block(safety_profile),
        "human_approval": _human_approval_block(list(approvals or [])),
        "review_focus_areas": list(REVIEW_FOCUS_AREAS),
    }


class KodyReviewAdapter:
    """Kody PR-review adapter — review-package builder and result recorder.

    Actual execution against the Kody/Kodus API is gated by
    `config.KODY_REVIEW_ENABLED` and is not implemented in this build. Even
    when invoked, `execute()` raises NotImplementedError so a misroute can
    never reach a network call.
    """

    provider: str = "kody"

    def prepare_review_package(
        self,
        *,
        pr_draft: PullRequestDraft,
        project: Project,
        code_repository: CodeRepository,
        safety_profile: RepoSafetyProfile | None = None,
        dev_task: DevTask | None = None,
        subtask: Subtask | None = None,
        requirement: Requirement | None = None,
        epic: Epic | None = None,
        tool_run: ToolRun | None = None,
        check_runs: list[CheckRun] | None = None,
        approvals: list[Approval] | None = None,
    ) -> dict:
        return build_kody_review_package(
            pr_draft=pr_draft,
            project=project,
            code_repository=code_repository,
            safety_profile=safety_profile,
            dev_task=dev_task,
            subtask=subtask,
            requirement=requirement,
            epic=epic,
            tool_run=tool_run,
            check_runs=check_runs,
            approvals=approvals,
        )

    def record_review_result(
        self,
        *,
        review: PullRequestReview,
        conclusion: PullRequestReviewConclusion,
        summary: str = "",
        findings: list[PullRequestReviewFinding] | None = None,
        recommendations: str | None = None,
        raw_output: str | None = None,
    ) -> PullRequestReview:
        now = datetime.now(timezone.utc)
        return review.model_copy(
            update={
                "status": "completed",
                "conclusion": conclusion,
                "summary": summary or review.summary,
                "findings": list(findings) if findings is not None else review.findings,
                "recommendations": (
                    recommendations if recommendations is not None else review.recommendations
                ),
                "raw_output": raw_output if raw_output is not None else review.raw_output,
                "completed_at": review.completed_at or now,
                "updated_at": now,
            }
        )

    def execute(self, *args, **kwargs):
        if not config.KODY_REVIEW_ENABLED:
            raise NotImplementedError("Kody review execution is disabled")
        raise NotImplementedError(
            "Kody external execution is not implemented in this build"
        )
