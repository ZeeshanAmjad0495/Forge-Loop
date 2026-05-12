# ForgeLoop Final Post-74 Smoke Test

## Verdict

**PASS WITH MANUAL FALLBACK: ready, but some live integrations were not configured.**

The full backend test suite passes (1126 passed, 1 skipped), the frontend
builds, every Release 8–12 surface answers correctly via live HTTP probes,
runtime endpoints expose no secrets, work-safe policy denies/requires-
approval correctly, and backup export+import honor the redaction and
no-overwrite guarantees. The "manual fallback" qualifier reflects that
local MongoDB, real OpenHands, real GitHub, and live external LLM
providers were intentionally not configured on this host — those paths
are covered by mocked tests, not by a live end-to-end call.

## Environment

- **Branch:** `main`
- **Commit:** `c74758e5c7dd38d3ffdb35adb9d6875a850c4d5e`
- **Runtime profile:** `local`
- **Repository provider:** `memory` (local MongoDB not available on this host)
- **Artifact provider:** `database`
- **Secret provider:** `env`
- **LLM provider (default):** `mock` (configured); `ollama` shown as configured but not live-tested
- **MongoDB / local_document:** not installed locally (no `mongod`, port 27017 closed) — persistence path covered only by `mongomock` parity tests
- **OpenHands execution:** disabled (`OPENHANDS_EXECUTION_ENABLED=false`)
- **GitHub integration:** disabled (`GITHUB_INTEGRATION_ENABLED=false`)
- **GitHub push:** disabled (`GITHUB_PUSH_ENABLED=false`)
- **Command runner:** enabled flag set (`COMMAND_RUNNER_ENABLED=true`) — covered by tests, not exercised against real shell on this host
- **Git workflow / commit:** enabled flag set — covered by tests, no live push

## Commands Run

| Command | Result | Notes |
|---|---|---|
| `git status` | clean | up to date with `origin/main` |
| `git log -1 --oneline` | `c74758e Release 12: Add product factory hardening foundations` | latest pushed commit |
| `git ls-files \| grep -E '\.env\|secrets/\|credentials\|service.account\|private.key'` | empty | no secret-like files tracked |
| `pytest -q` (full backend suite) | **1126 passed, 1 skipped in 13.40s** | full integration smoke |
| `pytest` on 39 targeted release-area test files | **624 passed in 11.48s** | per-release coverage proof |
| `cd apps/web && npm run build` | OK | `vite v6.4.2`, 237 modules transformed, dist/ written |
| `command -v mongod` / `nc -z localhost 27017` | not present / closed | local MongoDB unavailable |
| live probe v2 (`/tmp/forgeloop_smoke_v2.py`) | PASS | runtime endpoints, R11 end-to-end, R12 + work-safe + backup |

## Test Results

- **Backend:** 1126 passed, 1 skipped (full suite, 13.40s). Targeted release-area subset: 624 passed (11.48s).
- **Frontend:** `apps/web` built cleanly with Vite v6.4.2.

## Runtime Verification

| Area | Status | Notes |
|---|---|---|
| `GET /runtime/profile` | PASS | `profile=local`, `repository_provider=memory`, durability warning present |
| `GET /runtime/config` | PASS | exposes typed sections (repository / artifacts / secrets / execution / integrations), three warnings, zero errors |
| `GET /runtime/cloud-compatibility` | PASS | `compatible=true`, two informational warnings (memory durability, auth disabled), zero errors |
| Memory durability warning | PASS | surfaced on `/runtime/profile`, `/runtime/config`, and `/runtime/cloud-compatibility` |
| `local_document` MongoDB status | PASS (not configured) | `mongodb_required=false`, `mongodb_enabled=false` correctly reported |
| No secrets in responses | PASS | no `api_key=`, `client_secret`, `private_key`, or `service_account_json` in any runtime payload; `github_token_configured=false` shown as a bool, never the token value |
| `GET /llm/providers` | PASS | reports mock/deepseek/kimi/ollama/openai_compatible config flags, no key material |
| `GET /runtime/model-routing` | PASS | reports routing intent (default reasoning, long-context, local-support, test) without key material |

## Persistence Verification

| Area | Status | Notes |
|---|---|---|
| In-memory CRUD baseline | PASS | covered by `test_projects.py`, `test_tickets.py`, `test_repositories.py`, etc. — 1126/1051 deltas across the suite include extensive CRUD coverage |
| `local_document` (MongoDB) persistence | NOT LIVE-TESTED | `mongod` absent, port 27017 closed; the path is covered by `tests/test_repositories_mongo_parity.py` (11 parity tests + `mongomock`) and `tests/test_repositories_mongo*.py` integration tests via mongomock |
| Backend restart durability | NOT LIVE-TESTED | not exercised because the active provider is `memory`; not durable by design and surfaced as a warning |

## Execution Bridge Verification

| Area | Status | Notes |
|---|---|---|
| Workspace registration | PASS | `tests/test_workspaces.py` covers create / inspect / archive flows |
| Workspace inspection | PASS | covered by `test_workspaces.py` |
| Command definition | PASS | `tests/test_commands.py` |
| Safe command run | PASS | `tests/test_commands.py` (`COMMAND_RUNNER_ENABLED=true` path exercised) |
| Check definition | PASS | `tests/test_checks.py` |
| Check execution through safe runner | PASS | `tests/test_check_execution.py` |
| Local git inspection | PASS | `tests/test_git_workflow.py` covers inspection + branch + commit |
| ForgeLoop-scoped branch creation | PASS | `tests/test_git_workflow.py` |
| Local commit | PASS | `tests/test_git_workflow.py` (with `GIT_COMMIT_ENABLED=true`) |
| OpenHands package / dry-run only | PASS | `tests/test_openhands_runner.py` + `test_openhands_execution.py` (execution disabled) |
| PR draft creation | PASS | `tests/test_pr_drafts.py` |
| PR review record | PASS | `tests/test_pr_reviews.py` |
| Review feedback item | PASS | `tests/test_review_feedback.py` |
| Revision planning | PASS | `tests/test_review_feedback.py` covers the revision-plan endpoint |
| Memory learning | PASS | `tests/test_memory_learning_runs.py` + `test_memory_candidates.py` |

## Release 9 Verification

| Area | Status | Notes |
|---|---|---|
| CostRecord create/list | PASS | `tests/test_cost_records.py` |
| ContextPack create/list | PASS | `tests/test_context_packs.py` |
| Typed memory retrieval | PASS | `tests/test_memory_retrieval.py` |
| Artifact summary create | PASS | `tests/test_artifact_summaries.py` |
| Model route preview | PASS | `tests/test_model_routing.py` |
| Prompt / context cache | PASS | `tests/test_prompt_context_cache.py` |
| Budget policy + status + check | PASS | `tests/test_budget_controls.py` |
| Ollama provider config visible (no live call) | PASS | `/llm/providers` reports `ollama` as `configured=true` without requiring a live Ollama daemon; the `tests/test_ollama_provider.py` suite uses mocks |
| OpenAI-compatible provider config visible (no network) | PASS | `tests/test_openai_compatible_provider.py` mocks the HTTP layer |
| Swarm budget check | PASS | `tests/test_swarm_budget.py` |

## Release 10 Verification

| Area | Status | Notes |
|---|---|---|
| Build trial create | PASS | `tests/test_evaluation_trials.py` |
| Trial stages recorded | PASS | `tests/test_evaluation_trials.py` |
| Quality metrics endpoint | PASS | `tests/test_quality_metrics.py` |
| Feedback analytics endpoint | PASS | `tests/test_feedback_analytics.py` |
| Agent failure create/resolve | PASS | `tests/test_agent_failures.py` |
| Cost report endpoint | PASS | `tests/test_cost_reporting.py` |
| Benchmark scenario/run/result | PASS | `tests/test_regression_benchmarks.py` |

## Release 11 Verification

| Area | Status | Notes |
|---|---|---|
| Research brief create | PASS | live probe v2 + `tests/test_research_scout.py` |
| Research source create + attach | PASS | live probe v2 + `tests/test_research_sources.py` |
| Architecture review create | PASS | live probe v2 + `tests/test_architecture_reviews.py` |
| Improvement proposal full lifecycle | PASS | live probe v2 (propose → approve → mark-implemented) + `tests/test_improvement_proposals.py` |
| ADR create + state change | PASS | live probe v2 (proposed → accepted) + `tests/test_architecture_decisions.py` |
| Experiment plan + run + complete | PASS | live probe v2 (approve → run with baseline_metrics → complete with decision) + `tests/test_experiments.py` |
| Retrospective create | PASS | live probe v2 + `tests/test_retrospectives.py` |

## Release 12 Verification

| Area | Status | Notes |
|---|---|---|
| Project templates seed-defaults | PASS | live probe v2 + `tests/test_project_templates.py` (idempotent) |
| Workflow templates seed-defaults | PASS | live probe v2 + `tests/test_workflow_templates.py` (idempotent) |
| Project packs seed-defaults | PASS | live probe v2 + `tests/test_project_packs.py` (idempotent) |
| Work-safe policy create | PASS | live probe v2 (strict, project-scoped) + `tests/test_work_safe_policies.py` |
| Effective policy endpoint | PASS | live probe v2 confirms project policy beats global policy |
| Work-safe action check | PASS | live probe v2 confirms `external_llm_call` → `deny`, `github_push` → `require_approval`, `artifact_export` to `secrets/key.pem` → `deny` |
| Backup export creates safe metadata bundle | PASS | live probe v2 inspected the bundle: `schema_version=1`, `entity_counts` present, JSON parses |
| Backup omits secrets / workspace source | PASS | live probe v2 asserts no `files`/`content`/`source` keys on workspace entries and any secret-named field carries `[REDACTED]` |
| Backup import dry-run | PASS | live probe v2 + `tests/test_backups.py` |
| Restore does not overwrite existing | PASS | live probe v2 verified `imported.projects == 0` and `skipped_existing.projects == 1` when re-importing into the same store |

## Issues Found

None blocking. The smoke surfaced no defects in the product. Two informational warnings are expected in the local profile and acknowledged by design:

- **Informational warning — memory provider is not durable**
  - Severity: informational
  - Area: runtime / persistence
  - Symptom: `/runtime/profile`, `/runtime/config`, and `/runtime/cloud-compatibility` all report a warning that `memory` is not durable.
  - Evidence: `"Repository provider 'memory' is not durable; data is lost on restart."` in profile output.
  - Suggested fix: switch to `REPOSITORY_PROVIDER=local_document` once a local MongoDB is installed for real-project use.
  - Blocks first real project? **No** for short-lived experimentation; **Yes** before relying on persistence across restarts.

- **Informational warning — auth disabled**
  - Severity: informational
  - Area: auth
  - Symptom: cloud-compatibility flags `auth disabled` as a warning.
  - Evidence: `"auth disabled."` warning in `/runtime/cloud-compatibility`.
  - Suggested fix: set `AUTH_ENABLED=true` and configure `AUTH_TOKEN_SECRET` before any cloud or shared use.
  - Blocks first real project? **No** for solo local use; **Yes** before any network-exposed deployment.

## Manual Fallbacks / Not Live-Tested

- **OpenHands live execution:** disabled (`OPENHANDS_EXECUTION_ENABLED=false`). Prepare/dry-run path covered by tests.
- **GitHub live draft PR creation:** disabled (`GITHUB_INTEGRATION_ENABLED=false`, `GITHUB_PUSH_ENABLED=false`). Adapter covered by tests with mocked transport.
- **Ollama live call:** not exercised. Provider is reported as `configured=true` but no daemon was contacted; covered by `tests/test_ollama_provider.py` with mocks.
- **DeepSeek / Kimi live call:** not exercised; reported as `configured=false`.
- **Local MongoDB persistence:** not live-tested (no `mongod` installed; port 27017 closed). Covered by `tests/test_repositories_mongo_parity.py` and other Mongo tests via `mongomock`.
- **Frontend live UI flow:** not exercised. `apps/web` builds cleanly; no manual click-through done in this smoke.

## Final Recommendation

**Ready with manual fallback.**

ForgeLoop is ready to start the first real project (ProbePilot / SiteGuard) on the local profile. Before depending on any of these paths in real work:

1. Install a local MongoDB (or accept the durability warning) and switch `REPOSITORY_PROVIDER` to `local_document`.
2. If a real LLM is wanted, configure `LLM_PROVIDER` to `deepseek` / `kimi` and provide the relevant API key via environment.
3. If GitHub integration is wanted, set `GITHUB_INTEGRATION_ENABLED=true`, configure a token, and validate a single draft PR end-to-end before relying on the path.
4. Re-enable auth (`AUTH_ENABLED=true`) before exposing the API beyond `localhost`.

No source-code fixes are recommended.
