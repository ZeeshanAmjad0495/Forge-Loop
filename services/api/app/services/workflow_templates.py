"""Golden path workflow templates (Release 12, Task 71).

Stores reusable workflow templates for common work types (feature, bugfix,
refactor, security, etc.). The service does NOT execute workflows or
automatically create dev tasks; it records metadata and previews.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..models import (
    WorkflowStage,
    WorkflowTemplate,
    WorkflowTemplateCreate,
    WorkflowTemplatePreview,
    WorkflowTemplateUpdate,
)
from ..repositories import WorkflowTemplateRepository


def create_template(
    repo: WorkflowTemplateRepository,
    *,
    body: WorkflowTemplateCreate,
) -> WorkflowTemplate:
    now = datetime.now(timezone.utc)
    template = WorkflowTemplate(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        description=body.description,
        workflow_type=body.workflow_type,
        status=body.status,
        stages=[WorkflowStage(**s.model_dump()) for s in body.stages],
        default_required_checks=list(body.default_required_checks),
        approval_gates=list(body.approval_gates),
        review_checklist=list(body.review_checklist),
        memory_capture_rules=list(body.memory_capture_rules),
        recommended_models=list(body.recommended_models),
        tags=list(body.tags),
        created_at=now,
        updated_at=now,
    )
    repo.save(template)
    return template


def update_template(
    repo: WorkflowTemplateRepository,
    template: WorkflowTemplate,
    body: WorkflowTemplateUpdate,
) -> WorkflowTemplate:
    data = template.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = WorkflowTemplate(**data)
    repo.update(updated)
    return updated


def archive_template(
    repo: WorkflowTemplateRepository, template: WorkflowTemplate
) -> WorkflowTemplate:
    now = datetime.now(timezone.utc)
    data = template.model_dump()
    data["status"] = "archived"
    data["archived_at"] = now
    data["updated_at"] = now
    updated = WorkflowTemplate(**data)
    repo.update(updated)
    return updated


def build_preview(template: WorkflowTemplate) -> WorkflowTemplatePreview:
    return WorkflowTemplatePreview(
        template=template,
        stages=list(template.stages),
        required_checks=list(template.default_required_checks),
        approval_gates=list(template.approval_gates),
        review_checklist=list(template.review_checklist),
    )


# -- Default catalog ------------------------------------------------------

_FEATURE_STAGES = [
    {"name": "requirement", "stage_type": "requirement", "description": "Capture or analyze requirement."},
    {"name": "planning", "stage_type": "planning", "description": "Decompose into dev tasks."},
    {"name": "approval", "stage_type": "approval", "description": "Human approval before implementation."},
    {"name": "implement", "stage_type": "implement", "description": "Implementation, with tests."},
    {"name": "check", "stage_type": "check", "description": "Run required QA/security checks."},
    {"name": "review", "stage_type": "review", "description": "PR review (Kody/manual)."},
    {"name": "memory", "stage_type": "memory", "description": "Capture lessons into project memory."},
]

_BUGFIX_STAGES = [
    {"name": "reproduce", "stage_type": "requirement", "description": "Reproduce the bug with a failing test."},
    {"name": "diagnose", "stage_type": "planning", "description": "Identify root cause."},
    {"name": "approval", "stage_type": "approval", "description": "Human approval if scope grows."},
    {"name": "fix", "stage_type": "implement", "description": "Smallest safe fix."},
    {"name": "check", "stage_type": "check", "description": "Run regression tests."},
    {"name": "review", "stage_type": "review", "description": "PR review."},
    {"name": "memory", "stage_type": "memory", "description": "Record failure pattern."},
]

_REFACTOR_STAGES = [
    {"name": "baseline", "stage_type": "requirement", "description": "Capture current behavior with tests."},
    {"name": "plan", "stage_type": "planning", "description": "Plan small, reversible steps."},
    {"name": "approval", "stage_type": "approval", "description": "Approval before structural changes."},
    {"name": "refactor", "stage_type": "implement", "description": "Behavior-preserving refactor."},
    {"name": "check", "stage_type": "check", "description": "All tests still pass."},
    {"name": "review", "stage_type": "review", "description": "PR review."},
]

_SECURITY_STAGES = [
    {"name": "triage", "stage_type": "requirement", "description": "Confirm vulnerability scope/severity."},
    {"name": "plan", "stage_type": "planning", "description": "Plan minimal disclosure-safe fix."},
    {"name": "approval", "stage_type": "approval", "description": "Security owner approval."},
    {"name": "fix", "stage_type": "implement", "description": "Apply fix with secret hygiene."},
    {"name": "security_check", "stage_type": "check", "description": "Run Semgrep/Trivy/Gitleaks."},
    {"name": "review", "stage_type": "review", "description": "Security review."},
    {"name": "memory", "stage_type": "memory", "description": "Record security learning."},
]

_INCIDENT_STAGES = [
    {"name": "incident_link", "stage_type": "requirement", "description": "Link to incident record."},
    {"name": "root_cause", "stage_type": "planning", "description": "Root cause analysis."},
    {"name": "approval", "stage_type": "approval", "description": "Approval before remediation."},
    {"name": "remediate", "stage_type": "implement", "description": "Remediation work."},
    {"name": "check", "stage_type": "check", "description": "Verify no regressions."},
    {"name": "memory", "stage_type": "memory", "description": "Record incident learning."},
]

_TEST_HARDENING_STAGES = [
    {"name": "gap_analysis", "stage_type": "requirement", "description": "Identify untested or flaky areas."},
    {"name": "plan", "stage_type": "planning", "description": "Plan deterministic tests."},
    {"name": "implement", "stage_type": "implement", "description": "Add/replace tests; mock externals."},
    {"name": "check", "stage_type": "check", "description": "Run suite, ensure no flakes."},
    {"name": "review", "stage_type": "review", "description": "Review test changes."},
]


_DEFAULTS: list[dict[str, Any]] = [
    {
        "name": "Feature workflow",
        "slug": "feature",
        "description": "Golden path for new features.",
        "workflow_type": "feature",
        "stages": _FEATURE_STAGES,
        "default_required_checks": ["tests", "lint"],
        "approval_gates": ["pre_implementation", "pre_merge"],
        "review_checklist": [
            "Tests cover the new behavior.",
            "No unrelated changes.",
            "PR description explains the why.",
        ],
        "memory_capture_rules": [
            "Record new domain term if introduced.",
            "Record any non-obvious design decision.",
        ],
        "recommended_models": ["deepseek", "kimi"],
        "tags": ["golden-path"],
    },
    {
        "name": "Bugfix workflow",
        "slug": "bugfix",
        "description": "Golden path for bug fixes.",
        "workflow_type": "bugfix",
        "stages": _BUGFIX_STAGES,
        "default_required_checks": ["tests"],
        "approval_gates": ["pre_merge"],
        "review_checklist": [
            "Failing test added before fix.",
            "Smallest safe diff.",
        ],
        "memory_capture_rules": ["Record failure pattern."],
        "recommended_models": ["deepseek"],
        "tags": ["golden-path"],
    },
    {
        "name": "Refactor workflow",
        "slug": "refactor",
        "description": "Behavior-preserving refactor.",
        "workflow_type": "refactor",
        "stages": _REFACTOR_STAGES,
        "default_required_checks": ["tests"],
        "approval_gates": ["pre_implementation"],
        "review_checklist": [
            "Behavior unchanged.",
            "Tests still cover the original behavior.",
        ],
        "recommended_models": ["deepseek"],
        "tags": ["golden-path"],
    },
    {
        "name": "Security fix workflow",
        "slug": "security",
        "description": "Disclosure-safe security fix.",
        "workflow_type": "security",
        "stages": _SECURITY_STAGES,
        "default_required_checks": ["tests", "semgrep", "trivy", "gitleaks"],
        "approval_gates": ["pre_implementation", "pre_merge"],
        "review_checklist": [
            "No secrets in diff.",
            "Disclosure plan agreed.",
        ],
        "memory_capture_rules": ["Record security pattern."],
        "recommended_models": ["kimi"],
        "tags": ["golden-path", "security"],
    },
    {
        "name": "Incident follow-up workflow",
        "slug": "incident-followup",
        "description": "Follow-up work after an incident.",
        "workflow_type": "incident_followup",
        "stages": _INCIDENT_STAGES,
        "default_required_checks": ["tests"],
        "approval_gates": ["pre_merge"],
        "review_checklist": ["Linked to incident.", "Regression test added."],
        "memory_capture_rules": ["Record incident learning."],
        "recommended_models": ["kimi"],
        "tags": ["golden-path", "incident"],
    },
    {
        "name": "Test hardening workflow",
        "slug": "test-hardening",
        "description": "Improve coverage and reduce flake.",
        "workflow_type": "test_hardening",
        "stages": _TEST_HARDENING_STAGES,
        "default_required_checks": ["tests"],
        "approval_gates": [],
        "review_checklist": ["No new flakes.", "External deps mocked."],
        "recommended_models": ["deepseek"],
        "tags": ["golden-path", "qa"],
    },
]


def default_template_slugs() -> list[str]:
    return [d["slug"] for d in _DEFAULTS]


def seed_defaults(repo: WorkflowTemplateRepository) -> list[WorkflowTemplate]:
    seeded: list[WorkflowTemplate] = []
    for spec in _DEFAULTS:
        existing = repo.get_by_slug(spec["slug"])
        if existing is not None:
            seeded.append(existing)
            continue
        stage_models = [WorkflowStage(**s) for s in spec.get("stages", [])]
        body = WorkflowTemplateCreate(
            status="active",
            **{k: v for k, v in spec.items() if k != "stages"},
            stages=stage_models,
        )
        seeded.append(create_template(repo, body=body))
    return seeded
