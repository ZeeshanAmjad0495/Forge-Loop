"""Task 83: advisory-only auto-remediation proposals.

A RemediationProposal is a *draft* turned from a CI-failure analysis, an
incident analysis, or a PR-review's findings. It is advisory only:
ForgeLoop never auto-merges, auto-deploys, creates branches/PRs, or runs
destructive commands. A proposal only becomes executable work (a
DevTask) after an explicit human Approval.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RemediationSourceType = Literal["ci_analysis", "incident_analysis", "pr_review"]
RemediationSeverity = Literal["low", "medium", "high", "critical"]
RemediationApprovalStatus = Literal["pending", "approved", "rejected"]


class RemediationProposal(BaseModel):
    id: str
    project_id: str
    source_type: RemediationSourceType
    source_id: str
    severity: RemediationSeverity
    suspected_root_cause: str
    proposed_change: str
    risk: str
    tests_to_run: list[str] = []
    rollback_note: str
    approval_status: RemediationApprovalStatus = "pending"
    # Always true: advisory-only — a human must approve before any work.
    requires_human_approval: bool = True
    dev_task_id: str | None = None
    created_at: datetime
    updated_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
