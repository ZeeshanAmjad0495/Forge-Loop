"""Domain-specific project packs (Release 12, Task 72).

Bundles reusable context, templates, safety defaults, checks, and workflow
suggestions for common project domains. The service is metadata-only and
does NOT generate projects, run commands, install dependencies, or call
external services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..models import (
    ProjectPack,
    ProjectPackCreate,
    ProjectPackPreview,
    ProjectPackUpdate,
)
from ..repositories import ProjectPackRepository


def create_pack(
    repo: ProjectPackRepository,
    *,
    body: ProjectPackCreate,
) -> ProjectPack:
    now = datetime.now(timezone.utc)
    pack = ProjectPack(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        description=body.description,
        domain=body.domain,
        status=body.status,
        template_ids=list(body.template_ids),
        workflow_template_ids=list(body.workflow_template_ids),
        default_context=dict(body.default_context),
        suggested_memory=list(body.suggested_memory),
        suggested_required_checks=list(body.suggested_required_checks),
        suggested_blocked_paths=list(body.suggested_blocked_paths),
        suggested_command_definitions=list(body.suggested_command_definitions),
        suggested_budget_policy=dict(body.suggested_budget_policy),
        suggested_model_routing=dict(body.suggested_model_routing),
        tags=list(body.tags),
        created_at=now,
        updated_at=now,
    )
    repo.save(pack)
    return pack


def update_pack(
    repo: ProjectPackRepository,
    pack: ProjectPack,
    body: ProjectPackUpdate,
) -> ProjectPack:
    data = pack.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ProjectPack(**data)
    repo.update(updated)
    return updated


def archive_pack(repo: ProjectPackRepository, pack: ProjectPack) -> ProjectPack:
    now = datetime.now(timezone.utc)
    data = pack.model_dump()
    data["status"] = "archived"
    data["archived_at"] = now
    data["updated_at"] = now
    updated = ProjectPack(**data)
    repo.update(updated)
    return updated


def build_preview(pack: ProjectPack) -> ProjectPackPreview:
    return ProjectPackPreview(
        pack=pack,
        suggested_project_context=dict(pack.default_context),
        suggested_required_checks=list(pack.suggested_required_checks),
        suggested_blocked_paths=list(pack.suggested_blocked_paths),
        suggested_memory=list(pack.suggested_memory),
        suggested_command_definitions=list(pack.suggested_command_definitions),
        suggested_budget_policy=dict(pack.suggested_budget_policy),
        suggested_model_routing=dict(pack.suggested_model_routing),
        template_ids=list(pack.template_ids),
        workflow_template_ids=list(pack.workflow_template_ids),
    )


# -- Default catalog ------------------------------------------------------

_DEFAULTS: list[dict[str, Any]] = [
    {
        "name": "API Monitoring",
        "slug": "api-monitoring",
        "description": "Poll APIs, record uptime/latency, surface anomalies.",
        "domain": "api_monitoring",
        "default_context": {
            "domain_rules": "Keep observability local-first; no external telemetry by default.",
            "test_commands": "pytest",
        },
        "suggested_memory": [
            "Endpoint baselines must be recorded before alerting.",
        ],
        "suggested_required_checks": ["tests", "type_check"],
        "suggested_blocked_paths": [".env", "secrets/"],
        "suggested_command_definitions": [
            {"name": "Run probes", "command": "python -m app.probes"},
        ],
        "suggested_budget_policy": {"workflow_type": "probe", "max_runs_per_day": 1000},
        "suggested_model_routing": {"summarize": "ollama", "analyze": "deepseek"},
        "tags": ["monitoring", "observability"],
    },
    {
        "name": "QA Automation Tool",
        "slug": "qa-automation",
        "description": "Build a reusable QA harness (Playwright, axe-core).",
        "domain": "qa_automation",
        "default_context": {
            "test_commands": "pytest && npx playwright test",
        },
        "suggested_memory": ["Track flaky tests with retry counts."],
        "suggested_required_checks": ["tests", "e2e", "a11y"],
        "suggested_blocked_paths": [".env"],
        "suggested_command_definitions": [
            {"name": "Playwright", "command": "npx playwright test"},
        ],
        "suggested_budget_policy": {
            "workflow_type": "qa",
            "max_runs_per_day": 200,
        },
        "suggested_model_routing": {"summarize": "ollama", "analyze": "deepseek"},
        "tags": ["qa", "stlc"],
    },
    {
        "name": "Web Scraping & Reporting",
        "slug": "web-scraping-reporting",
        "description": "Scrape allow-listed sources and produce reports.",
        "domain": "web_scraping_reporting",
        "default_context": {
            "domain_rules": "Respect robots.txt; only scrape allow-listed domains.",
        },
        "suggested_memory": [
            "Record robots.txt and ToS for every allow-listed source.",
        ],
        "suggested_required_checks": ["tests"],
        "suggested_blocked_paths": [".env", "scraped_data/raw/"],
        "suggested_command_definitions": [
            {"name": "Scrape", "command": "python -m app.scrape"},
        ],
        "suggested_budget_policy": {
            "workflow_type": "scrape",
            "max_runs_per_day": 50,
        },
        "suggested_model_routing": {"summarize": "ollama", "extract": "deepseek"},
        "tags": ["scraping", "reporting"],
    },
    {
        "name": "AI Assistant",
        "slug": "ai-assistant",
        "description": "Local-first AI assistant with optional hosted fallback.",
        "domain": "ai_assistant",
        "default_context": {
            "domain_rules": "Default to Ollama; never send customer data to hosted LLMs without approval.",
        },
        "suggested_memory": [
            "Track user-specific assistant preferences.",
        ],
        "suggested_required_checks": ["tests"],
        "suggested_blocked_paths": [".env", "secrets/", "models/"],
        "suggested_command_definitions": [],
        "suggested_budget_policy": {
            "workflow_type": "ai_assistant",
            "max_tokens_per_day": 200000,
        },
        "suggested_model_routing": {
            "summarize": "ollama",
            "reason": "deepseek",
            "long_context": "kimi",
        },
        "tags": ["ai", "local-first"],
    },
    {
        "name": "Finance Tracker",
        "slug": "finance-tracker",
        "description": "Personal/SMB finance tracker with local-first data.",
        "domain": "finance_tracker",
        "default_context": {
            "domain_rules": "Financial data never leaves the local environment by default.",
        },
        "suggested_memory": ["Track recurring categories and merchants."],
        "suggested_required_checks": ["tests", "lint"],
        "suggested_blocked_paths": [".env", "data/", "exports/"],
        "suggested_command_definitions": [],
        "suggested_budget_policy": {
            "workflow_type": "finance",
            "max_tokens_per_day": 50000,
        },
        "suggested_model_routing": {"summarize": "ollama", "classify": "deepseek"},
        "tags": ["finance", "local-first"],
    },
]


def default_pack_slugs() -> list[str]:
    return [d["slug"] for d in _DEFAULTS]


def seed_defaults(repo: ProjectPackRepository) -> list[ProjectPack]:
    seeded: list[ProjectPack] = []
    for spec in _DEFAULTS:
        existing = repo.get_by_slug(spec["slug"])
        if existing is not None:
            seeded.append(existing)
            continue
        body = ProjectPackCreate(status="active", **spec)
        seeded.append(create_pack(repo, body=body))
    return seeded
