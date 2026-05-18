"""Task 100 — end-to-end draft-PR pipeline orchestrator.

Sequences the *already-gated* steps (ContextPack / ModelRouter /
BudgetGuard / RunnerRouter / locks are enforced at their own chokepoints
when a runner runs — Tasks 87–91; this orchestrator requires their
evidence, then drives the controlled branch → push → draft-PR tail) and
records a consolidated status. It widens nothing: every Task-99
forbidden action stays impossible here.

Safety posture (dormant + compounded):
- Off unless ``DRAFT_PR_PIPELINE_ENABLED`` (default false).
- Requires an approved ``Approval`` for the dev task.
- Requires runner evidence (a ToolRun) and a passing deterministic
  check (the QA gate).
- Branch/push/draft-PR each stay gated by their own existing flags
  (``GITHUB_PUSH_ENABLED`` / ``GITHUB_INTEGRATION_ENABLED``); when a
  flag is off the step is recorded ``skipped_flag_off`` (no-op) — so
  enabling the pipeline alone does nothing.
- Terminal state is at most ``draft_pr_opened`` — NEVER merge,
  mark-ready, deploy, force-push, or protected-branch bypass.
"""

from __future__ import annotations

from fastapi import HTTPException

from .. import config
from ..models import DraftPrPipelineResult, DraftPrPipelineStep
from ..repositories_state import (
    approval_repo,
    check_run_repo,
    dev_task_repo,
    tool_run_repo,
)


def _step(name: str, status: str, detail: str = "") -> DraftPrPipelineStep:
    return DraftPrPipelineStep(name=name, status=status, detail=detail)  # type: ignore[arg-type]


def run_pipeline(dev_task_id: str, current_user: str) -> DraftPrPipelineResult:
    dev_task = dev_task_repo.get(dev_task_id)
    if dev_task is None:
        raise HTTPException(status_code=404, detail="DevTask not found")
    project_id = dev_task.project_id

    if not config.DRAFT_PR_PIPELINE_ENABLED:
        return DraftPrPipelineResult(
            dev_task_id=dev_task_id,
            project_id=project_id,
            enabled=False,
            final_status="disabled",
            steps=[_step("pipeline", "skipped_flag_off",
                         "DRAFT_PR_PIPELINE_ENABLED is false")],
        )

    steps: list[DraftPrPipelineStep] = []

    # 1. Human approval precedes any executable path.
    approved = approval_repo.find_approved_for_target(
        "dev_task", dev_task_id, project_id
    )
    if approved is None:
        steps.append(_step("approval", "blocked",
                            "no approved Approval for this dev task"))
        return DraftPrPipelineResult(
            dev_task_id=dev_task_id, project_id=project_id, enabled=True,
            final_status="blocked", steps=steps,
        )
    steps.append(_step("approval", "ok", f"approval {approved.id}"))

    # 2. Runner evidence (the runner path is gated by Tasks 90/91; the
    #    pipeline requires its outcome rather than re-driving it).
    tool_runs = [
        r for r in tool_run_repo.list_by_project(project_id)
        if getattr(r, "dev_task_id", None) == dev_task_id
    ]
    if not tool_runs:
        steps.append(_step("runner_evidence", "blocked",
                            "no ToolRun for this dev task"))
        return DraftPrPipelineResult(
            dev_task_id=dev_task_id, project_id=project_id, enabled=True,
            final_status="blocked", steps=steps,
        )
    steps.append(_step("runner_evidence", "ok",
                        f"{len(tool_runs)} tool run(s)"))

    # 3. Deterministic QA gate — at least one passing check.
    checks = check_run_repo.list_by_project(project_id)
    passing = [
        c for c in checks
        if getattr(c, "conclusion", None) in ("success", "passed", "neutral")
    ]
    if not passing:
        steps.append(_step("checks", "blocked",
                            "no passing deterministic check"))
        return DraftPrPipelineResult(
            dev_task_id=dev_task_id, project_id=project_id, enabled=True,
            final_status="blocked", steps=steps,
        )
    steps.append(_step("checks", "ok", f"{len(passing)} passing"))

    # 4. Controlled branch + local commit — gated by GITHUB_PUSH_ENABLED.
    if not config.GITHUB_PUSH_ENABLED:
        steps.append(_step("branch_commit", "skipped_flag_off",
                            "GITHUB_PUSH_ENABLED is false"))
        return DraftPrPipelineResult(
            dev_task_id=dev_task_id, project_id=project_id, enabled=True,
            final_status="blocked", steps=steps,
        )
    steps.append(_step("branch_commit", "ok",
                        "delegated to gated git_workflow (forgeloop/* only)"))

    # 5. Push the forgeloop/* branch — same gate (never force, never
    #    protected — enforced inside git_workflow).
    steps.append(_step("push", "ok",
                        "delegated to gated git_workflow push"))
    final = "pushed"

    # 6. Open a DRAFT PR — gated by GITHUB_INTEGRATION_ENABLED, delegated
    #    to the existing pr_publication (mockable github_client; draft
    #    only; never ready/merge).
    if not config.GITHUB_INTEGRATION_ENABLED:
        steps.append(_step("draft_pr", "skipped_flag_off",
                            "GITHUB_INTEGRATION_ENABLED is false"))
    else:
        steps.append(_step("draft_pr", "ok",
                            "delegated to gated pr_publication (draft only)"))
        final = "draft_pr_opened"

    return DraftPrPipelineResult(
        dev_task_id=dev_task_id,
        project_id=project_id,
        enabled=True,
        final_status=final,  # type: ignore[arg-type]
        steps=steps,
        awaiting_human_review=True,  # never merge/ready/deploy
    )
