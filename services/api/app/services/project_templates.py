"""Project template library service (Release 12, Task 70).

Stores reusable project templates and seeds a small set of defaults. The
service does NOT create projects, workspaces, repos, or run commands — it
records metadata/instructions only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..models import (
    ProjectTemplate,
    ProjectTemplateCreate,
    ProjectTemplatePreview,
    ProjectTemplateUpdate,
)
from ..repositories import ProjectTemplateRepository


def create_template(
    repo: ProjectTemplateRepository,
    *,
    body: ProjectTemplateCreate,
) -> ProjectTemplate:
    now = datetime.now(timezone.utc)
    template = ProjectTemplate(
        id=str(uuid.uuid4()),
        name=body.name,
        slug=body.slug,
        description=body.description,
        template_type=body.template_type,
        status=body.status,
        stack=list(body.stack),
        tags=list(body.tags),
        default_context=dict(body.default_context),
        suggested_required_checks=list(body.suggested_required_checks),
        suggested_blocked_paths=list(body.suggested_blocked_paths),
        suggested_workflows=list(body.suggested_workflows),
        file_manifest=list(body.file_manifest),
        instructions=body.instructions,
        created_at=now,
        updated_at=now,
    )
    repo.save(template)
    return template


def update_template(
    repo: ProjectTemplateRepository,
    template: ProjectTemplate,
    body: ProjectTemplateUpdate,
) -> ProjectTemplate:
    data = template.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ProjectTemplate(**data)
    repo.update(updated)
    return updated


def archive_template(
    repo: ProjectTemplateRepository, template: ProjectTemplate
) -> ProjectTemplate:
    now = datetime.now(timezone.utc)
    data = template.model_dump()
    data["status"] = "archived"
    data["archived_at"] = now
    data["updated_at"] = now
    updated = ProjectTemplate(**data)
    repo.update(updated)
    return updated


def list_active(
    repo: ProjectTemplateRepository,
) -> list[ProjectTemplate]:
    return [t for t in repo.list_all() if t.status == "active"]


def build_preview(template: ProjectTemplate) -> ProjectTemplatePreview:
    return ProjectTemplatePreview(
        template=template,
        suggested_project_context=dict(template.default_context),
        suggested_required_checks=list(template.suggested_required_checks),
        suggested_blocked_paths=list(template.suggested_blocked_paths),
        suggested_workflows=list(template.suggested_workflows),
    )


# -- Default catalog ------------------------------------------------------

_DEFAULTS: list[dict[str, Any]] = [
    {
        "name": "FastAPI backend API",
        "slug": "fastapi-backend",
        "description": "Minimal FastAPI service with pytest, Pydantic, and Uvicorn.",
        "template_type": "backend_api",
        "stack": ["python", "fastapi", "pydantic", "pytest", "uvicorn"],
        "tags": ["api", "python", "local-first"],
        "default_context": {
            "test_commands": "pytest",
            "deployment_commands": "uvicorn app.main:app --host 0.0.0.0 --port 8080",
        },
        "suggested_required_checks": ["tests", "type_check"],
        "suggested_blocked_paths": [".env", "secrets/"],
        "suggested_workflows": ["plan", "implement", "check", "review"],
        "file_manifest": [
            "app/main.py",
            "app/models.py",
            "tests/test_health.py",
            "pyproject.toml",
        ],
        "instructions": "Start with /health, add Pydantic models, write pytest first.",
    },
    {
        "name": "React frontend app",
        "slug": "react-frontend",
        "description": "Minimal React + Vite frontend with TypeScript and ESLint.",
        "template_type": "frontend_app",
        "stack": ["typescript", "react", "vite", "eslint"],
        "tags": ["frontend", "ui", "local-first"],
        "default_context": {
            "test_commands": "npm test",
            "deployment_commands": "npm run build",
        },
        "suggested_required_checks": ["lint", "build"],
        "suggested_blocked_paths": [".env", "node_modules/"],
        "suggested_workflows": ["plan", "implement", "check", "review"],
        "file_manifest": [
            "src/main.tsx",
            "src/App.tsx",
            "package.json",
            "vite.config.ts",
        ],
        "instructions": "Keep UI minimal. Render markdown for any generated artifacts.",
    },
    {
        "name": "Full-stack FastAPI + React",
        "slug": "fullstack-fastapi-react",
        "description": "Backend FastAPI service plus a React/Vite frontend in a monorepo.",
        "template_type": "full_stack_app",
        "stack": ["python", "fastapi", "typescript", "react", "vite"],
        "tags": ["fullstack", "monorepo"],
        "default_context": {
            "test_commands": "pytest && npm test",
        },
        "suggested_required_checks": ["tests", "lint", "build"],
        "suggested_blocked_paths": [".env", "node_modules/", "secrets/"],
        "suggested_workflows": ["plan", "implement", "check", "review"],
        "file_manifest": [
            "services/api/app/main.py",
            "apps/web/src/main.tsx",
        ],
        "instructions": "Keep backend and frontend independently buildable.",
    },
    {
        "name": "CLI automation tool",
        "slug": "cli-automation-tool",
        "description": "Python CLI with click/typer and pytest.",
        "template_type": "cli_tool",
        "stack": ["python", "typer", "pytest"],
        "tags": ["cli", "automation"],
        "default_context": {"test_commands": "pytest"},
        "suggested_required_checks": ["tests"],
        "suggested_blocked_paths": [".env"],
        "suggested_workflows": ["plan", "implement", "check"],
        "file_manifest": ["src/cli.py", "tests/test_cli.py", "pyproject.toml"],
        "instructions": "Treat every subcommand as a small, testable unit.",
    },
    {
        "name": "QA automation tool",
        "slug": "qa-automation-tool",
        "description": "Test-runner harness with Playwright/axe-core templates.",
        "template_type": "qa_automation",
        "stack": ["python", "playwright", "axe-core", "pytest"],
        "tags": ["qa", "stlc"],
        "default_context": {
            "test_commands": "pytest && npx playwright test",
        },
        "suggested_required_checks": ["tests", "a11y", "e2e"],
        "suggested_blocked_paths": [".env"],
        "suggested_workflows": ["plan", "implement", "check", "review"],
        "file_manifest": ["tests/e2e/", "tests/a11y/"],
        "instructions": "Keep e2e and a11y suites isolated from unit tests.",
    },
    {
        "name": "Local AI assistant",
        "slug": "local-ai-assistant",
        "description": "Local-first AI assistant skeleton using Ollama by default.",
        "template_type": "ai_assistant",
        "stack": ["python", "ollama", "fastapi"],
        "tags": ["ai", "local-first"],
        "default_context": {
            "test_commands": "pytest",
            "deployment_commands": "uvicorn app.main:app",
        },
        "suggested_required_checks": ["tests"],
        "suggested_blocked_paths": [".env", "secrets/", "models/"],
        "suggested_workflows": ["plan", "implement", "check"],
        "file_manifest": ["app/main.py", "app/providers.py"],
        "instructions": "Default to a local provider; never call hosted LLMs in tests.",
    },
]


def default_template_slugs() -> list[str]:
    return [d["slug"] for d in _DEFAULTS]


def seed_defaults(repo: ProjectTemplateRepository) -> list[ProjectTemplate]:
    """Idempotently seed the default templates.

    For each default, if a template with the same slug already exists the
    existing record is returned unchanged. Otherwise a new template is
    created with status ``active``.
    """
    seeded: list[ProjectTemplate] = []
    for spec in _DEFAULTS:
        existing = repo.get_by_slug(spec["slug"])
        if existing is not None:
            seeded.append(existing)
            continue
        body = ProjectTemplateCreate(status="active", **spec)
        seeded.append(create_template(repo, body=body))
    return seeded
