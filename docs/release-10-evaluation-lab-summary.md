# Release 10 — Evaluation Lab Summary

Release 10 adds the Evaluation Lab foundation: structured measurement of
ForgeLoop project-build attempts, quality metrics, human feedback patterns,
agent failure classification, cost-per-feature reporting, and a regression
benchmark suite.

This release is **measurement-only**. It does not run projects, evaluator
agents, swarms, or LLMs. Callers (humans or future agents) record outcomes;
the lab turns them into queryable records and summaries.

## Task list

| # | Task | Highlights |
|---|------|-----------|
| 57 | Project build trial framework | `ProjectBuildTrial` + `ProjectBuildTrialStage` models / repos / service / API. Trial lifecycle: planned → running → completed/failed with verdict. Stage `linked_*_id` fields tie back to existing check/command/tool/PR-review/feedback records. `GET /build-trials/{id}` returns a summary with stage-status counts. |
| 58 | Quality metrics foundation | `QualityMetricSnapshot` model (optional persisted) + `services.quality_metrics`. Endpoints `GET /projects/{id}/quality-metrics`, `GET /build-trials/{id}/quality-metrics`, `POST /build-trials/{id}/quality-metrics/snapshot`. Counts stages, check/command/tool runs (success/failure), PR reviews (derived via PR drafts), feedback (blocking/resolved), memory candidates. |
| 59 | Human feedback analytics | `services.feedback_analytics`. Endpoints `GET /projects/{id}/feedback-analytics`, `GET /pr-drafts/{id}/feedback-analytics`. Counts by severity, status, category, source, plus revision-work-item created/resolved totals. |
| 60 | Agent failure taxonomy | `AgentFailureRecord` model + repo + service + full CRUD endpoints (`POST/GET/PATCH /agent-failures`, `POST /resolve`, `GET /summary`). Taxonomy enums: 19 categories (e.g. `failing_tests`, `unsafe_path_touch`, `cost_budget_exceeded`), 5 severities, 4 statuses, 5 detectors. Summary endpoint groups by category / severity / status / source. |
| 61 | Cost-per-feature reporting | `services.cost_reporting` aggregates Release 9 `CostRecord` data. Endpoints `/projects/{id}/cost-report`, `/build-trials/{id}/cost-report`, `/dev-tasks/{id}/cost-report`, `/requirements/{id}/cost-report`. Groups by provider / model / source_type / workflow_type. Added `build_trial` to `CostRecordSourceType` so trial-level cost reports can find their records. |
| 62 | Regression benchmark suite | `BenchmarkScenario` / `BenchmarkRun` / `BenchmarkRunResult` models + repos + service + endpoints for scenarios, runs, and results. Scenarios are project-scoped or global. No execution layer — results are recorded by callers via `POST /benchmark-runs/{id}/results`. |

## New entities

| Model | Purpose |
|-------|---------|
| `ProjectBuildTrial`, `ProjectBuildTrialStage` | Build-trial state machine + per-stage evidence links. |
| `ProjectBuildTrialSummary` | Response shape: trial + stage-status counts. |
| `QualityMetricSnapshot` + `QualityMetricsResponse` | Persisted snapshot model + live response. |
| `AgentFailureRecord` + `AgentFailureSummary` | Failure classification + project-level counters. |
| `BenchmarkScenario`, `BenchmarkRun`, `BenchmarkRunResult` | Benchmark scaffolding. |

All models have memory, MongoDB (`local_document`), and Firestore repository
implementations. Five new collections wired into the Mongo `_INDEX_PLAN`
(`project_build_trials`, `project_build_trial_stages`,
`quality_metric_snapshots`, `agent_failure_records`,
`benchmark_scenarios`, `benchmark_runs`, `benchmark_run_results`).

## New routes (32)

Build trials:
- `POST/GET /projects/{id}/build-trials`
- `GET/PATCH /build-trials/{id}` (GET returns summary with stage counts)
- `POST/GET /build-trials/{id}/stages`
- `PATCH /build-trial-stages/{id}`
- `POST /build-trials/{id}/complete`

Quality metrics:
- `GET /projects/{id}/quality-metrics`
- `GET /build-trials/{id}/quality-metrics`
- `POST /build-trials/{id}/quality-metrics/snapshot`

Feedback analytics:
- `GET /projects/{id}/feedback-analytics`
- `GET /pr-drafts/{id}/feedback-analytics`

Agent failures:
- `POST/GET /projects/{id}/agent-failures`
- `GET/PATCH /agent-failures/{id}`
- `POST /agent-failures/{id}/resolve`
- `GET /projects/{id}/agent-failures/summary`

Cost reporting:
- `GET /projects/{id}/cost-report`
- `GET /build-trials/{id}/cost-report`
- `GET /dev-tasks/{id}/cost-report`
- `GET /requirements/{id}/cost-report`

Benchmarks:
- `POST/GET /benchmark-scenarios`
- `GET/PATCH /benchmark-scenarios/{id}`
- `POST/GET /benchmark-scenarios/{id}/runs`
- `GET /benchmark-runs/{id}`
- `POST/GET /benchmark-runs/{id}/results`

## Tests

- Full backend suite: **963 passed, 1 skipped** (the Mongo *integration* test
  skips when no real Mongo server is reachable; Mongo *parity* tests run via
  `mongomock` and cover the new repositories).
- 6 new test files (one per task), ≈44 new tests.
- No real LLM, GCP, Mongo, or network calls.

## Frontend

- No frontend files were changed in Release 10.
- Per Release 10 rules, frontend build is skipped when no frontend files
  changed — even though `apps/web` exists. UI for Evaluation Lab is a
  candidate follow-up (Release 11+).

## What is still out of scope (parked)

- Real evaluator agents / multi-agent swarms.
- Automated failure detection (the taxonomy is *manual classification*; no
  automatic source ingestion yet).
- Live LLM-driven scenario evaluation in benchmark runs.
- Background workers / schedulers for periodic metric snapshots.
- ResearchScout, Architecture Review Agent, ADR workflow.
- Project templates, backup/export/restore.
- Marketing / SaaS billing workflows.
- New execution runners / new model providers (Release 9 set is unchanged).

## Known follow-ups

- `pr_review_repo` has no `list_by_project`; project-level quality metrics
  derive PR-review count via the project's PR drafts. If reviews ever need
  to span drafts not in the project's set, add a direct query.
- `CostRecordSourceType` gained `build_trial`; existing callers that branch
  on the literal should be reviewed.
- Snapshots are created on demand; no periodic capture yet. Wiring a cron or
  end-of-trial hook is the natural next step.
- Benchmark run execution is purely external — results are posted by the
  caller. Hooking the model-routing/cost layer when a benchmark run is
  actually executed remains for a later task.

## Final state

- Tests: 963 passed, 1 skipped.
- Frontend build: not required (no frontend changes).
- Commit/push: **not performed** — awaiting human review of this summary.
