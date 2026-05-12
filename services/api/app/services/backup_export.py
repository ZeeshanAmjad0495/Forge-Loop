"""Backup / export / restore service (Release 12, Task 74).

Produces JSON metadata bundles for projects or the full local workspace and
supports dry-run / create-new import for a safe subset of entities. The
service deliberately:

- omits secrets, ``.env``, credentials, private keys
- omits artifact ``content`` bodies that may carry PII
- omits workspace source files
- never overwrites existing records

The shape is a thin envelope::

    {
        "schema_version": 1,
        "exported_at": "...",
        "export_type": "project",
        "project_id": "...",
        "entity_counts": {...},
        "entities": {
            "projects": [...],
            ...
        }
    }
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from ..models import (
    Artifact,
    BackupExport,
    BackupExportCreate,
    BackupImport,
    BackupImportCreate,
)
from ..repositories import (
    ArtifactRepository,
    BackupExportRepository,
    BackupImportRepository,
    Repositories,
)

SCHEMA_VERSION = 1

# Field names that look like secrets and should be redacted in entity dumps.
_SENSITIVE_FIELDS = {
    "api_key",
    "secret",
    "password",
    "token",
    "private_key",
    "client_secret",
    "service_account_json",
    "github_token",
}

# Artifact fields we drop on export (the binary/text body is intentionally
# omitted; metadata is preserved).
_DROP_FROM_ARTIFACT = {"content"}


def _redact(value: dict[str, Any], drop: set[str] = frozenset()) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in value.items():
        if k in drop:
            continue
        if any(s in k.lower() for s in _SENSITIVE_FIELDS):
            out[k] = "[REDACTED]"
            continue
        out[k] = v
    return out


def _dump(items: list[BaseModel], *, drop: set[str] = frozenset()) -> list[dict[str, Any]]:
    return [_redact(item.model_dump(mode="json"), drop=drop) for item in items]


def _safe_list(repo: Any, method: str, *args, **kwargs) -> list[Any]:
    fn = getattr(repo, method, None)
    if fn is None:
        return []
    try:
        return list(fn(*args, **kwargs))
    except Exception:
        return []


# Entities included in a project-scoped export and the repo+lookup behind each.
def _project_entities(repos: Repositories, project_id: str) -> dict[str, list[dict[str, Any]]]:
    project = repos.project.get(project_id)
    projects = [project] if project is not None else []
    project_context = repos.project_context.get(project_id)
    return {
        "projects": _dump(projects),
        "project_contexts": _dump(
            [project_context] if project_context is not None else []
        ),
        "tickets": _dump(_safe_list(repos.ticket, "list_by_project", project_id)),
        "requirements": _dump(
            _safe_list(repos.requirement, "list_by_project", project_id)
        ),
        "dev_tasks": _dump(_safe_list(repos.dev_task, "list_by_project", project_id)),
        "epics": _dump(_safe_list(repos.epic, "list_by_project", project_id)),
        "approvals": _dump(_safe_list(repos.approval, "list_by_project", project_id)),
        "audit_events": _dump(
            _safe_list(repos.audit_event, "list_by_project", project_id)
        ),
        "code_repositories": _dump(
            _safe_list(repos.code_repository, "list_by_project", project_id)
        ),
        "check_definitions": _dump(
            _safe_list(repos.check_definition, "list_by_project", project_id)
        ),
        "tool_runner_definitions": _dump(
            _safe_list(repos.tool_runner_definition, "list_by_project", project_id)
        ),
        "command_definitions": _dump(
            _safe_list(repos.command_definition, "list_by_project", project_id)
        ),
        "workspaces": _dump(
            _safe_list(repos.workspace, "list_by_project", project_id)
        ),
        "memory_candidates": _dump(
            _safe_list(repos.memory_candidate, "list_by_project", project_id)
        ),
        "incidents": _dump(
            _safe_list(repos.incident, "list_by_project", project_id)
        ),
        "ci_events": _dump(_safe_list(repos.ci_event, "list_by_project", project_id)),
        "swarm_policies": _dump(
            _safe_list(repos.swarm_policy, "list_by_project", project_id)
        ),
        "budget_policies": _dump(
            _safe_list(repos.budget_policy, "list_by_project", project_id)
        ),
        "research_briefs": _dump(
            _safe_list(repos.research_brief, "list_by_project", project_id)
        ),
        "research_sources": _dump(
            _safe_list(repos.research_source, "list_by_project", project_id)
        ),
        "architecture_reviews": _dump(
            _safe_list(repos.architecture_review, "list_by_project", project_id)
        ),
        "improvement_proposals": _dump(
            _safe_list(repos.improvement_proposal, "list_by_project", project_id)
        ),
        "architecture_decisions": _dump(
            _safe_list(repos.architecture_decision, "list_by_project", project_id)
        ),
        "experiment_plans": _dump(
            _safe_list(repos.experiment_plan, "list_by_project", project_id)
        ),
        "project_retrospectives": _dump(
            _safe_list(repos.project_retrospective, "list_by_project", project_id)
        ),
        "work_safe_policies": _dump(
            _safe_list(repos.work_safe_policy, "list_by_project", project_id)
        ),
    }


def _full_entities(repos: Repositories) -> dict[str, list[dict[str, Any]]]:
    return {
        "projects": _dump(_safe_list(repos.project, "list_all")),
        "project_templates": _dump(_safe_list(repos.project_template, "list_all")),
        "workflow_templates": _dump(_safe_list(repos.workflow_template, "list_all")),
        "project_packs": _dump(_safe_list(repos.project_pack, "list_all")),
        "work_safe_policies": _dump(_safe_list(repos.work_safe_policy, "list_all")),
        "research_briefs": _dump(_safe_list(repos.research_brief, "list_all")),
        "research_sources": _dump(_safe_list(repos.research_source, "list_all")),
        "architecture_reviews": _dump(_safe_list(repos.architecture_review, "list_all")),
        "improvement_proposals": _dump(
            _safe_list(repos.improvement_proposal, "list_all")
        ),
        "architecture_decisions": _dump(
            _safe_list(repos.architecture_decision, "list_all")
        ),
        "experiment_plans": _dump(_safe_list(repos.experiment_plan, "list_all")),
        "project_retrospectives": _dump(
            _safe_list(repos.project_retrospective, "list_all")
        ),
    }


def _templates_only(repos: Repositories) -> dict[str, list[dict[str, Any]]]:
    return {
        "project_templates": _dump(_safe_list(repos.project_template, "list_all")),
        "workflow_templates": _dump(_safe_list(repos.workflow_template, "list_all")),
        "project_packs": _dump(_safe_list(repos.project_pack, "list_all")),
    }


def _audit_only(repos: Repositories, project_id: str | None) -> dict[str, list[dict[str, Any]]]:
    if project_id is not None:
        events = _safe_list(repos.audit_event, "list_by_project", project_id)
    else:
        events = _safe_list(repos.audit_event, "list_all")
    return {"audit_events": _dump(events)}


def _build_entities(
    repos: Repositories, body: BackupExportCreate
) -> dict[str, list[dict[str, Any]]]:
    if body.export_type == "project":
        if body.project_id is None:
            raise ValueError("project_id is required for export_type='project'")
        return _project_entities(repos, body.project_id)
    if body.export_type == "full_metadata":
        return _full_entities(repos)
    if body.export_type == "templates_only":
        return _templates_only(repos)
    if body.export_type == "audit_only":
        return _audit_only(repos, body.project_id)
    if body.export_type == "selected_entities":
        # scope is a list of entity names; cover what we know about.
        all_entities = _full_entities(repos)
        return {k: v for k, v in all_entities.items() if k in set(body.scope)}
    # custom — empty by default; caller can extend later
    return {}


def export_bundle(
    repos: Repositories,
    export_repo: BackupExportRepository,
    artifact_repo: ArtifactRepository,
    *,
    body: BackupExportCreate,
) -> tuple[BackupExport, Artifact, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    try:
        entities = _build_entities(repos, body)
    except ValueError as exc:
        record = BackupExport(
            id=str(uuid.uuid4()),
            project_id=body.project_id,
            export_type=body.export_type,
            status="failed",
            format=body.format,
            scope=list(body.scope),
            created_at=now,
            updated_at=now,
            error_message=str(exc),
        )
        export_repo.save(record)
        raise

    counts = {k: len(v) for k, v in entities.items()}
    bundle: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": now.isoformat(),
        "export_type": body.export_type,
        "project_id": body.project_id,
        "scope": list(body.scope),
        "entity_counts": counts,
        "entities": entities,
    }

    artifact = Artifact(
        id=str(uuid.uuid4()),
        artifact_type="backup_export",
        content=json.dumps(bundle, default=str),
        created_at=now,
    )
    artifact_repo.save(artifact)

    record = BackupExport(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        export_type=body.export_type,
        status="completed",
        format=body.format,
        scope=list(body.scope),
        artifact_id=artifact.id,
        summary={
            "schema_version": SCHEMA_VERSION,
            "entity_counts": counts,
        },
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    export_repo.save(record)
    return record, artifact, bundle


# -- Import --------------------------------------------------------------


def _load_bundle(
    artifact_repo: ArtifactRepository,
    body: BackupImportCreate,
) -> dict[str, Any]:
    if body.bundle is not None:
        return body.bundle
    if body.source_artifact_id is not None:
        artifact = artifact_repo.get(body.source_artifact_id)
        if artifact is None:
            raise ValueError("source_artifact_id does not resolve to a stored artifact")
        try:
            return json.loads(artifact.content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Stored artifact is not valid JSON: {exc}") from exc
    raise ValueError("Either bundle or source_artifact_id is required")


def _validate_bundle(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        errors.append("bundle is not an object")
        return errors
    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"unexpected schema_version: {bundle.get('schema_version')!r}; expected {SCHEMA_VERSION}"
        )
    if not isinstance(bundle.get("entities"), dict):
        errors.append("entities must be an object")
    return errors


# Entity name -> repo attribute on Repositories. Limited to safe-to-restore
# metadata entities. Workspaces, audit events, secrets, etc. are intentionally
# excluded from create_new mode.
_IMPORTABLE: dict[str, str] = {
    "projects": "project",
    "project_templates": "project_template",
    "workflow_templates": "workflow_template",
    "project_packs": "project_pack",
    "work_safe_policies": "work_safe_policy",
    "research_sources": "research_source",
    "research_briefs": "research_brief",
    "architecture_reviews": "architecture_review",
    "improvement_proposals": "improvement_proposal",
    "architecture_decisions": "architecture_decision",
    "project_retrospectives": "project_retrospective",
}


def _model_for(name: str):
    # Import lazily to avoid circular imports at module load time.
    from .. import models as _m

    return {
        "projects": _m.Project,
        "project_templates": _m.ProjectTemplate,
        "workflow_templates": _m.WorkflowTemplate,
        "project_packs": _m.ProjectPack,
        "work_safe_policies": _m.WorkSafePolicy,
        "research_sources": _m.ResearchSource,
        "research_briefs": _m.ResearchBrief,
        "architecture_reviews": _m.ArchitectureReview,
        "improvement_proposals": _m.ImprovementProposal,
        "architecture_decisions": _m.ArchitectureDecisionRecord,
        "project_retrospectives": _m.ProjectRetrospective,
    }[name]


def import_bundle(
    repos: Repositories,
    import_repo: BackupImportRepository,
    artifact_repo: ArtifactRepository,
    *,
    body: BackupImportCreate,
) -> BackupImport:
    now = datetime.now(timezone.utc)
    record_id = str(uuid.uuid4())
    try:
        bundle = _load_bundle(artifact_repo, body)
    except ValueError as exc:
        record = BackupImport(
            id=record_id,
            project_id=body.project_id,
            source_artifact_id=body.source_artifact_id,
            mode=body.mode,
            status="failed",
            summary=None,
            created_at=now,
            updated_at=now,
            error_message=str(exc),
        )
        import_repo.save(record)
        return record

    errors = _validate_bundle(bundle)
    entities = bundle.get("entities", {}) if isinstance(bundle, dict) else {}
    counts_seen = {k: len(v) for k, v in entities.items() if isinstance(v, list)}

    plan = {
        "would_import": {},
        "would_skip_existing": {},
        "would_skip_unsupported": {},
    }
    for entity_name, items in entities.items():
        if not isinstance(items, list):
            continue
        if entity_name not in _IMPORTABLE:
            plan["would_skip_unsupported"][entity_name] = len(items)
            continue
        repo = getattr(repos, _IMPORTABLE[entity_name])
        importable = 0
        existing = 0
        for item in items:
            ident = item.get("id") if isinstance(item, dict) else None
            if ident is None:
                continue
            current = repo.get(ident) if hasattr(repo, "get") else None
            if current is not None:
                existing += 1
            else:
                importable += 1
        plan["would_import"][entity_name] = importable
        plan["would_skip_existing"][entity_name] = existing

    if body.mode == "dry_run":
        summary = {
            "validation_errors": errors,
            "entity_counts_seen": counts_seen,
            "plan": plan,
        }
        record = BackupImport(
            id=record_id,
            project_id=body.project_id,
            source_artifact_id=body.source_artifact_id,
            mode=body.mode,
            status="completed",
            summary=summary,
            created_at=now,
            updated_at=now,
            completed_at=now,
            error_message=None,
        )
        import_repo.save(record)
        return record

    if errors:
        record = BackupImport(
            id=record_id,
            project_id=body.project_id,
            source_artifact_id=body.source_artifact_id,
            mode=body.mode,
            status="failed",
            summary={"validation_errors": errors},
            created_at=now,
            updated_at=now,
            completed_at=now,
            error_message="; ".join(errors),
        )
        import_repo.save(record)
        return record

    imported: dict[str, int] = {}
    skipped: dict[str, int] = {}
    for entity_name, items in entities.items():
        if not isinstance(items, list) or entity_name not in _IMPORTABLE:
            continue
        repo = getattr(repos, _IMPORTABLE[entity_name])
        model_cls = _model_for(entity_name)
        for item in items:
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            if ident is None:
                continue
            if repo.get(ident) is not None:
                skipped[entity_name] = skipped.get(entity_name, 0) + 1
                if body.mode == "merge_skip_existing":
                    continue
                # create_new also skips existing IDs (never overwrite)
                continue
            try:
                instance = model_cls.model_validate(item)
            except Exception:  # pragma: no cover - defensive
                skipped[entity_name] = skipped.get(entity_name, 0) + 1
                continue
            repo.save(instance)
            imported[entity_name] = imported.get(entity_name, 0) + 1

    summary = {
        "validation_errors": errors,
        "entity_counts_seen": counts_seen,
        "imported": imported,
        "skipped_existing": skipped,
    }
    record = BackupImport(
        id=record_id,
        project_id=body.project_id,
        source_artifact_id=body.source_artifact_id,
        mode=body.mode,
        status="completed",
        summary=summary,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    import_repo.save(record)
    return record
