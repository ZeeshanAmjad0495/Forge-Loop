# Release 12 — Product Factory Hardening

Status: complete (Tasks 70–74). MVP-foundation grade; not commit-pushed yet
pending human review.

## Tasks completed

- **Task 70 — Project template library**: `ProjectTemplate` records with
  six seeded defaults (FastAPI API, React frontend, Full-stack FastAPI +
  React, CLI automation, QA automation, Local AI assistant). Preview
  endpoint surfaces suggested project context / required checks / blocked
  paths / workflows.
- **Task 71 — Golden path workflow templates**: `WorkflowTemplate` records
  with six seeded defaults (feature, bugfix, refactor, security,
  incident-followup, test-hardening). Each template ships stages,
  approval gates, review checklist, memory capture rules, and recommended
  models. Preview endpoint included.
- **Task 72 — Domain-specific project packs**: `ProjectPack` records that
  bundle template ids, workflow template ids, suggested checks, blocked
  paths, command definitions, budget policy, and model routing. Five
  seeded defaults (API monitoring, QA automation, Web scraping &
  reporting, AI assistant, Finance tracker).
- **Task 73 — Work-safe enterprise hardening**: `WorkSafePolicy` records
  with project-scoped or global reach, action allow/deny flags, restricted
  providers/integrations, blocked path patterns, and `policy_level`
  (`personal` / `strict` / `enterprise_candidate`). Service computes the
  effective policy for a project and answers per-action check requests
  (`external_llm_call`, `github_push`, `openhands_execution`, etc.). The
  release also adds an `AuditExportRequest` model (metadata only).
- **Task 74 — Backup / export / restore**: JSON metadata bundle export
  with `schema_version`, `exported_at`, `entity_counts`, and a redaction
  step that strips `api_key`, `secret`, `password`, `token`, `private_key`,
  `client_secret`, `service_account_json`, `github_token`. Artifact body
  fields and workspace source files are omitted. Import supports
  `dry_run`, `create_new`, and `merge_skip_existing` (never overwrites
  existing records).

## Entities added

- `ProjectTemplate` (`models/project_templates.py`)
- `WorkflowTemplate` + `WorkflowStage` (`models/workflow_templates.py`)
- `ProjectPack` (`models/project_packs.py`)
- `WorkSafePolicy` + `AuditExportRequest` (`models/work_safe.py`)
- `BackupExport` + `BackupImport` (`models/backups.py`)

Each entity has in-memory + Firestore + MongoDB repository implementations
with indexes added to `_INDEX_PLAN`. All entities are wired through the
`Repositories` dataclass, the `get_repositories()` factory, and the
`repositories_state.py` singletons.

## Audit + artifact

New `AuditAction` values:

- `project_template_created/updated/archived/seeded`
- `workflow_template_created/updated/archived/seeded`
- `project_pack_created/updated/archived/seeded`
- `work_safe_policy_created/updated/archived`
- `work_safe_action_checked`
- `audit_export_requested/updated`
- `backup_export_requested/completed/failed`
- `backup_import_dry_run_completed/completed/failed`

New `artifact_type` value:

- `backup_export`

## APIs added (~50 endpoints across 5 routers)

Project templates (Task 70):

- `POST /project-templates`, `GET /project-templates`
- `GET /project-templates/{template_id}`, `PATCH /project-templates/{template_id}`
- `POST /project-templates/{template_id}/archive`
- `POST /project-templates/seed-defaults`
- `GET /project-templates/by-slug/{slug}`
- `POST /project-templates/{template_id}/preview`

Workflow templates (Task 71):

- `POST /workflow-templates`, `GET /workflow-templates`
- `GET /workflow-templates/{template_id}`, `PATCH /workflow-templates/{template_id}`
- `POST /workflow-templates/{template_id}/archive`
- `POST /workflow-templates/seed-defaults`
- `GET /workflow-templates/by-slug/{slug}`
- `POST /workflow-templates/{template_id}/preview`

Project packs (Task 72):

- `POST /project-packs`, `GET /project-packs`
- `GET /project-packs/{pack_id}`, `PATCH /project-packs/{pack_id}`
- `POST /project-packs/{pack_id}/archive`
- `POST /project-packs/seed-defaults`
- `GET /project-packs/by-slug/{slug}`
- `POST /project-packs/{pack_id}/preview`

Work-safe policies (Task 73):

- `POST /work-safe-policies`, `GET /work-safe-policies`
- `GET /work-safe-policies/{policy_id}`, `PATCH /work-safe-policies/{policy_id}`
- `POST /work-safe-policies/{policy_id}/archive`
- `GET /projects/{project_id}/work-safe-policies`
- `GET /projects/{project_id}/work-safe-policy/effective`
- `POST /projects/{project_id}/work-safe-policy/check`

Backups (Task 74):

- `POST /backups/exports`, `GET /backups/exports`
- `GET /backups/exports/{export_id}`
- `GET /projects/{project_id}/backups/exports`
- `POST /backups/imports/dry-run`, `POST /backups/imports`
- `GET /backups/imports/{import_id}`

## Tests

Full backend suite after Task 74:

```
1126 passed, 1 skipped in 12.72s
```

New test modules (Release 12):

- `tests/test_project_templates.py`
- `tests/test_workflow_templates.py`
- `tests/test_project_packs.py`
- `tests/test_work_safe_policies.py`
- `tests/test_backups.py`

All tests run with mocked / in-memory repositories — no LLM, network, GCP,
or MongoDB calls. The Mongo parity test (`tests/test_repositories_mongo_parity.py`)
covers the new repositories via `mongomock`.

Frontend was not modified in Release 12. Frontend build was therefore not
run, per the release rules.

## Known follow-ups (deliberately out of scope)

- Automatic project generation from a template / pack (would create
  workspaces, run commands, etc.).
- Full enterprise SaaS surface (orgs, teams, SSO, RBAC overhaul, billing,
  compliance certifications, live DLP scanners).
- Background backup scheduler and encrypted/cloud backups.
- Destructive overwrite mode for imports.
- Broad enforcement of work-safe policies across every route (current
  implementation is opt-in via the `check` endpoint).
- Marketplace / public sharing of templates and packs.
- UI for any of the above; no frontend work was done.

## Boundary preserved

The release does not:

- generate full projects, create workspaces/branches/PRs, or run commands;
- implement SaaS billing, multi-tenant orgs, SSO, RBAC overhaul, or
  marketing workflows;
- add deployment automation or new coding runners;
- run real swarms or background schedulers;
- enable autonomous self-modification;
- export secrets, `.env`, credentials, private keys, or workspace source
  files;
- overwrite existing data on import.

## Commit / push status

Not committed and not pushed. Per the release runner instructions, the
summary is presented first for human review before any commit/push action.
