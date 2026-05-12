# Release 8 — Local-first + Cloud-optional Runtime Summary

## Tasks completed

- **41 — Local-first runtime profile.** Added `FORGELOOP_RUNTIME_PROFILE`
  (default `local`), `RuntimeProfile` service, sanitized
  `GET /runtime/profile` endpoint, and a sanitized startup log line. No
  silent rewrite of `REPOSITORY_PROVIDER`; profile mismatches surface as
  warnings/errors.
- **42 — Local document provider cleanup.** Verified provider parity
  across every entity in the `Repositories` dataclass; expanded the
  `_INDEX_PLAN` with `status`, `created_at`, and `source_type+source_id`
  composite indexes; added parity/index/serialization tests using
  `mongomock`. No model changes; no Firestore collection renames.
- **43 — Filesystem artifact store.** Added
  `ARTIFACT_STORAGE_PROVIDER=database|filesystem`, optional `storage_*`
  fields on `Artifact` (backward compatible), and an
  `artifact_storage` service. Two high-value call sites migrated
  (`command_runner.py`, `openhands_execution.py` output artifact). Path
  traversal rejected; size + sha256 recorded.
- **44 — Env/local secret provider.** Added `SECRET_PROVIDER=env`,
  `app.services.secrets` with `get_secret` / `require_secret` /
  `redact_secret_value`. GitHub token resolution in `pr_publication`
  now consults the provider first, then falls back to `config.GITHUB_TOKEN`.
- **45 — Runtime profile config.** Added
  `GET /runtime/config` returning a resolved view of profile,
  repository, artifacts, secrets, execution toggles, and integration
  state with profile-aware warnings/errors. No secrets exposed.
- **46 — Cloud profile compatibility check.** Added
  `GET /runtime/cloud-compatibility` returning per-check
  `pass | warning | fail` status for repository, artifacts, command
  runner, OpenHands, git workflow, GitHub integration, auth, CORS,
  secrets provider, and Firestore config.

## What changed

- New service modules: `runtime_profile.py`, `runtime_config.py`,
  `cloud_compatibility.py`, `secrets.py`, `artifact_storage.py`.
- New route module: `runtime.py` exposing three auth-protected endpoints
  (`/runtime/profile`, `/runtime/config`, `/runtime/cloud-compatibility`).
- `Artifact` model gained optional storage metadata fields without
  breaking existing inline-content callers.
- `_INDEX_PLAN` in `repositories_mongo.py` aligned with the Task 42
  requirements (status, created_at, source_type+source_id).
- Sanitized startup log line written via lifespan.

## Local recommended config

```env
FORGELOOP_RUNTIME_PROFILE=local
REPOSITORY_PROVIDER=local_document
LOCAL_DOCUMENT_DB_PROVIDER=mongodb
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=forgeloop_local
ARTIFACT_STORAGE_PROVIDER=filesystem
ARTIFACT_FILESYSTEM_ROOT=./.forgeloop/artifacts
SECRET_PROVIDER=env
```

Memory mode remains the test default and is explicitly flagged as
non-durable in both the runtime summary and the cloud compatibility
report.

## Tests run

- Full backend pytest suite: **819 passed, 1 skipped**.
- New test files:
  - `tests/test_runtime_profile.py`
  - `tests/test_runtime_config.py`
  - `tests/test_cloud_compatibility.py`
  - `tests/test_repositories_mongo_parity.py`
  - `tests/test_artifact_storage.py`
  - `tests/test_secret_provider.py`
- Frontend build: skipped (no frontend files changed in Release 8).

## Known risks / follow-ups

- Most existing `Artifact(...)` call sites still construct artifacts
  inline rather than going through `artifact_storage.store_artifact`.
  Two high-value sites were migrated (command runner output, OpenHands
  execution output). Remaining sites can be migrated incrementally;
  they continue to work because the new `Artifact` fields are optional.
- `read_artifact_content` is provided for filesystem-backed reads but
  no existing route currently serves artifact content over HTTP;
  retrieval integration is a future task.
- Cloud compatibility check is a static config inspection; it does not
  perform real GCP/Firestore network calls and does not validate
  service account permissions.
- Mongo `_ensure_indexes` is run unconditionally on startup; if hosted
  Mongo restricts index creation, this would surface as a connection
  error rather than silent failure.

## Not implemented yet

- CostRecord
- ContextPack
- model routing
- Ollama provider
- OpenAI-compatible provider
- Evaluation Lab
- ResearchScout
- templates
- backup / export / restore
- cloud secret managers (GCP Secret Manager, Vault, etc.)
- migration of remaining Artifact construction call sites
- frontend runtime/settings UI

## No commit / push performed

All Release 8 changes remain uncommitted pending review.
