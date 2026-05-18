"""Task 83: advisory-only auto-remediation.

Turns a CI-failure analysis, an incident analysis, or a PR-review's
findings into a RemediationProposal *draft*. It never merges, deploys,
creates branches/PRs, or runs destructive commands. A proposal becomes
executable work (a DevTask) only after an explicit human Approval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from .. import config
from ..models import DevTask, RemediationProposal
from ..repositories_state import (
    approval_repo,
    audit_writer,
    ci_analysis_repo,
    dev_task_repo,
    incident_analysis_repo,
    pr_review_repo,
    remediation_proposal_repo,
)

_SEVERITY_PRIORITY = {
    "critical": "high",
    "high": "high",
    "medium": "medium",
    "low": "low",
}
_HIGH_CI = {"code_regression"}
_HIGH_INCIDENT = {"security_issue", "code_regression", "data_issue"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_enabled() -> None:
    if not config.AUTO_REMEDIATION_ENABLED:
        raise HTTPException(
            status_code=409,
            detail="auto-remediation is disabled (AUTO_REMEDIATION_ENABLED)",
        )


def _join(items: list[str], fallback: str) -> str:
    cleaned = [s.strip() for s in (items or []) if s and s.strip()]
    return "\n".join(f"- {s}" for s in cleaned) if cleaned else fallback


def _tests_for(areas: list[str]) -> list[str]:
    areas = [a.strip() for a in (areas or []) if a and a.strip()]
    if not areas:
        return ["full backend test suite"]
    return [f"tests covering {a}" for a in areas]


def _persist(proposal: RemediationProposal, actor: str) -> RemediationProposal:
    remediation_proposal_repo.save(proposal)
    try:  # Task 96 metric (no-op if disabled)
        from .metrics import record_remediation_proposal

        record_remediation_proposal(proposal.source_type)
    except Exception:
        pass
    audit_writer.write(
        "remediation_proposal_created",
        "remediation_proposal",
        proposal.id,
        project_id=proposal.project_id,
        actor_email=actor,
        details={
            "source_type": proposal.source_type,
            "source_id": proposal.source_id,
            "severity": proposal.severity,
        },
    )
    return proposal


def propose_from_ci_analysis(
    ci_analysis_id: str, actor: str
) -> RemediationProposal:
    _require_enabled()
    analysis = ci_analysis_repo.get(ci_analysis_id)
    if analysis is None or analysis.status != "completed":
        raise HTTPException(
            status_code=404, detail="completed CI analysis not found"
        )
    severity = "high" if analysis.conclusion in _HIGH_CI else "medium"
    if analysis.conclusion == "flaky_test":
        severity = "low"
    now = _now()
    proposal = RemediationProposal(
        id=str(uuid.uuid4()),
        project_id=analysis.project_id,
        source_type="ci_analysis",
        source_id=analysis.id,
        severity=severity,  # type: ignore[arg-type]
        suspected_root_cause=_join(
            analysis.likely_root_causes,
            analysis.summary or "Unknown CI failure root cause.",
        ),
        proposed_change=_join(
            analysis.suggested_fixes,
            "No concrete fix suggested; human investigation required.",
        ),
        risk=(
            f"Severity {severity}. Advisory only — review before any "
            "code change; no automated merge/deploy."
        ),
        tests_to_run=_tests_for(analysis.affected_areas),
        rollback_note=(
            "Revert the proposed change. No production mutation is "
            "performed by ForgeLoop (advisory-only)."
        ),
        created_at=now,
        updated_at=now,
    )
    return _persist(proposal, actor)


def propose_from_incident_analysis(
    incident_analysis_id: str, actor: str
) -> RemediationProposal:
    _require_enabled()
    analysis = incident_analysis_repo.get(incident_analysis_id)
    if analysis is None or analysis.status != "completed":
        raise HTTPException(
            status_code=404, detail="completed incident analysis not found"
        )
    severity = "high" if analysis.conclusion in _HIGH_INCIDENT else "medium"
    now = _now()
    proposal = RemediationProposal(
        id=str(uuid.uuid4()),
        project_id=analysis.project_id,
        source_type="incident_analysis",
        source_id=analysis.id,
        severity=severity,  # type: ignore[arg-type]
        suspected_root_cause=_join(
            analysis.likely_root_causes,
            analysis.summary or "Unknown incident root cause.",
        ),
        proposed_change=_join(
            analysis.remediation_plan,
            "No remediation plan produced; human investigation required.",
        ),
        risk=(
            f"Severity {severity}. Advisory only — incident remediation "
            "must be human-approved; no automated merge/deploy/rollback."
        ),
        tests_to_run=_tests_for(analysis.affected_areas),
        rollback_note=(
            "Revert the proposed change. ForgeLoop performs no "
            "production mutation or rollback (advisory-only)."
        ),
        created_at=now,
        updated_at=now,
    )
    return _persist(proposal, actor)


def propose_from_pr_review(
    review_id: str, actor: str
) -> RemediationProposal:
    _require_enabled()
    review = pr_review_repo.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="PR review not found")
    findings = list(review.findings or [])
    sevs = {str(f.severity or "").lower() for f in findings}
    if "blocking" in sevs:
        severity = "high"
    elif "warning" in sevs:
        severity = "medium"
    else:
        severity = "low"
    root = review.summary or (
        findings[0].message if findings else "PR review findings."
    )
    change = _join(
        [
            f.recommendation or f.message
            for f in findings
            if (f.recommendation or f.message)
        ],
        review.recommendations or "Address the PR-review findings.",
    )
    now = _now()
    proposal = RemediationProposal(
        id=str(uuid.uuid4()),
        project_id=review.project_id,
        source_type="pr_review",
        source_id=review.id,
        severity=severity,  # type: ignore[arg-type]
        suspected_root_cause=root,
        proposed_change=change,
        risk=(
            f"Severity {severity}. Advisory only — apply via the normal "
            "review/runner gate after human approval; no auto-merge."
        ),
        tests_to_run=["full backend test suite"],
        rollback_note=(
            "Revert the proposed change; advisory-only, no production "
            "mutation performed."
        ),
        created_at=now,
        updated_at=now,
    )
    return _persist(proposal, actor)


def _get_or_404(proposal_id: str) -> RemediationProposal:
    p = remediation_proposal_repo.get(proposal_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail="remediation proposal not found"
        )
    return p


def approve_proposal(proposal_id: str, actor: str) -> RemediationProposal:
    _require_enabled()
    proposal = _get_or_404(proposal_id)
    if proposal.approval_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"proposal already {proposal.approval_status}",
        )
    # Human approval gate: a DevTask is created ONLY when an approved
    # Approval row exists for this proposal. Advisory-only.
    if config.AUTO_REMEDIATION_CREATE_TASKS_REQUIRE_APPROVAL:
        approved = approval_repo.find_approved_for_target(
            "remediation_proposal", proposal.id, proposal.project_id
        )
        if approved is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "approval required for remediation_proposal before "
                    "creating a DevTask"
                ),
            )
    now = _now()
    task = DevTask(
        id=str(uuid.uuid4()),
        project_id=proposal.project_id,
        source_analysis_id=(
            proposal.source_id
            if proposal.source_type != "pr_review"
            else None
        ),
        agent_run_id=f"remediation:{proposal.id}",
        title=f"Remediation: {proposal.suspected_root_cause[:80]}",
        description=(
            f"Source: {proposal.source_type} {proposal.source_id}\n"
            f"Severity: {proposal.severity}\n\n"
            f"Proposed change:\n{proposal.proposed_change}\n\n"
            f"Rollback: {proposal.rollback_note}"
        ),
        task_type="unknown",
        status="proposed",
        priority=_SEVERITY_PRIORITY.get(proposal.severity, "medium"),
        acceptance_criteria=list(proposal.tests_to_run),
        definition_of_done=[
            "Human-reviewed remediation applied via the normal gate",
            "Listed tests pass",
        ],
        qa_required=True,
        created_at=now,
        updated_at=now,
    )
    dev_task_repo.save(task)
    updated = proposal.model_copy(
        update={
            "approval_status": "approved",
            "dev_task_id": task.id,
            "decided_by": actor,
            "decided_at": now,
            "updated_at": now,
        }
    )
    remediation_proposal_repo.update(updated)
    audit_writer.write(
        "remediation_proposal_approved",
        "remediation_proposal",
        proposal.id,
        project_id=proposal.project_id,
        actor_email=actor,
        details={"dev_task_id": task.id},
    )
    return updated


def reject_proposal(proposal_id: str, actor: str) -> RemediationProposal:
    _require_enabled()
    proposal = _get_or_404(proposal_id)
    if proposal.approval_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"proposal already {proposal.approval_status}",
        )
    now = _now()
    updated = proposal.model_copy(
        update={
            "approval_status": "rejected",
            "decided_by": actor,
            "decided_at": now,
            "updated_at": now,
        }
    )
    remediation_proposal_repo.update(updated)
    audit_writer.write(
        "remediation_proposal_rejected",
        "remediation_proposal",
        proposal.id,
        project_id=proposal.project_id,
        actor_email=actor,
        details={},
    )
    return updated


def auto_remediation_runtime_summary() -> dict:
    return {
        "enabled": config.AUTO_REMEDIATION_ENABLED,
        "advisory_only": config.AUTO_REMEDIATION_ADVISORY_ONLY,
        "create_tasks_require_approval": (
            config.AUTO_REMEDIATION_CREATE_TASKS_REQUIRE_APPROVAL
        ),
        "allow_branch_creation": config.AUTO_REMEDIATION_ALLOW_BRANCH_CREATION,
        "allow_pr_creation": config.AUTO_REMEDIATION_ALLOW_PR_CREATION,
        "auto_merge": False,
        "auto_deploy": False,
    }
