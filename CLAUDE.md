# CLAUDE.md

# ForgeLoop — Claude Code Instructions

You are the primary coding agent for this repository.

ForgeLoop is a human-supervised autonomous SDLC + STLC control plane. It helps manage projects, requirements, tickets, agent runs, artifacts, approvals, QA loops, code review loops, and tool-runner workflows.

ForgeLoop is the control plane. It should not rebuild coding agents from scratch. When possible, future code execution should be delegated to existing tools such as OpenHands, Aider, Cline, OpenCode, Hermes Agent, TestZeus, Playwright Test Agents, Kodus/Kody, PR-Agent, Semgrep, OSV-Scanner, Trivy, axe-core, and similar tools.

## Current Build State

Releases 1–6 are implemented (all 32 tasks complete).

Implemented capabilities include:

- FastAPI backend
- React/Vite frontend
- Admin auth/login
- Ticket creation and retrieval
- Planning AgentRun and Artifact workflow
- Mock, DeepSeek, and Kimi LLM providers
- Per-request provider selection
- Firestore repository support
- Dockerized backend
- Backend CI
- Terraform minimum GCP infrastructure
- Cloud Run deploy workflow
- Project-aware dashboard and project context/memory
- Structured requirements intake and requirement analysis
- Task/subtask decomposition and task lifecycle management
- Human approval gates and audit events
- Repo connection + repo safety profile
- Deterministic QA/security check definitions and check runs (Semgrep, Trivy, Gitleaks, axe-core, Playwright, etc.)
- Langfuse tracing (prompt versions, cost, token records)
- ToolRunner abstraction + OpenHandsRunner (dry-run foundation)
- PR draft workflow (task output → PR draft tracking)
- Kodus/Kody PR review integration (tracking + adapter foundation)
- CI failure ingestion and advisory analysis
- Production/incident ticket workflow and advisory triage
- Project memory learning loop (human-supervised candidate flow)

Post-Release-6 hardening & capability work (shipped):

- OpenHands HTTP execution bridge + automated stale-runtime reaper (launchd)
- Real Aider execution bridge (subprocess via local Ollama; gated, audited, snapshot-diffed) — Aider is a true coding runner, not package-only
- Native multi-dev-task integration endpoint (`POST /workspaces/{id}/integration-runs`) — ordered merge, structured 409 on conflict, never silent-drops a member
- B1 sandbox state-bleed elimination (pre-execute hard-sync, incl. disposable migration-stamped DB cleanup)
- B3 latency attribution (sandbox-resolve vs agent-run phase timing; configurable resolve cap)
- Real Kody/Kodus HTTP review adapter (CLI-key API: submit/poll, contract-verified) + Langfuse observability provider (live-verified; optional, no-op without creds)
- Per-workspace execution mutual-exclusion (concurrency hardening)
- Security: OWASP-aligned audit + fixes — see `docs/security-architecture.md` and `docs/security-audit-findings.md`. All feature/execution/push gates default OFF; auth/secret/SSRF/injection/confinement controls enforced without changing usability.

All 32 core tasks are complete. The post-32 controlled-adoption roadmap
(Tasks 75–85) is also complete. **Release 10 — Operational Execution
Layer (Tasks 86–100) is also complete** (authorized by Task 86 via an
explicit `docs/roadmap.md` update; all 15 tasks implemented, tested, and
pushed). Release 10 wired already-built cost/router/context/runner/
observability foundations into real execution; it added no new product
surface beyond Tasks 86–100. No work beyond Task 100 without a further
explicit `docs/roadmap.md` update.

## Active Roadmap

The fixed core engineering roadmap is 32 tasks across 6 releases. All
six are complete. The bounded post-32 controlled-adoption roadmap
(Tasks 75–85) is also complete. **Release 10 — Operational Execution
Layer (Tasks 86–100) is also complete** (authorized by Task 86; see
`docs/roadmap.md`). There is no active release; no work beyond Task 100
may start without a further explicit `docs/roadmap.md` update.

- Release 1: Core planning platform — complete
- Release 2: Provider + usability + project context — complete
- Release 3: Requirements + task planning engine — complete
- Release 4: Golden path + deterministic QA — complete
- Release 5: Tool runner + PR workflow (OpenHands primary) — complete
- Release 6: CI + incident + learning loop — complete
- Post-32 controlled adoption: Tasks 75–85 — complete
- Release 10: Operational Execution Layer (Tasks 86–100) — complete

Release 10 is bounded to Tasks 86–100. It wires existing
ModelRouter / CostRecord / BudgetGuard / ContextPack / RunnerRouter /
locks / observability foundations into real execution, plus optional
Phase-B infra adapters (Temporal/NATS/Valkey, all config-gated, DB
remains source of truth) and a controlled draft-PR path (never
merge/deploy). No work beyond Task 100 without a further
`docs/roadmap.md` update.

> Note: `docs/release-8…release-12-*-summary.md` are historical
> exploratory artifacts from an earlier numbering experiment and are
> **not** the authoritative release scheme. In particular
> `docs/release-10-evaluation-lab-summary.md` (old Tasks 57–62) is
> unrelated to this Release 10. The authoritative scheme is: Releases
> 1–6 (Tasks 1–32) + controlled adoption (Tasks 75–85) + Release 10
> (Tasks 86–100). Historical summaries are preserved, never deleted.

See `docs/roadmap.md` for full scope and `docs/tooling-strategy.md` for tool choices.

Future ForgeLoop Studio modules are parked and must not be implemented unless explicitly requested:

- ProductScout
- AuditLens
- LaunchPilot

Marketing/product-growth workflows are future scope only.

## Core Principles

1. Keep changes small and reviewable.
2. Do not add speculative features.
3. Do not skip ahead to future releases.
4. Do not rebuild existing open-source coding/QA/review tools from scratch.
5. Prefer adapters, orchestration, audit trails, approvals, and project memory.
6. Do not expose secrets.
7. Do not send proprietary/customer data to external LLMs unless explicitly approved.
8. Do not merge, deploy, or remediate production without human approval.
9. Tests must not call real LLMs, real GCP services, or network services unless explicitly requested.
10. Mock external providers in automated tests.

## Runtime Profiles

ForgeLoop is cloud-supported, not cloud-dependent. The same codebase runs in three profiles:

| Profile | Storage | LLM | Secrets | Cloud |
|---------|---------|-----|---------|-------|
| local | InMemory (dev) → SQLite/local Postgres (future) | Mock / Ollama / DeepSeek / Kimi | env vars | Not required |
| hybrid | Local storage | Hosted LLM if configured | env vars | GitHub optional |
| cloud | Firestore | Any configured provider | Secret Manager | Cloud Run |

Profile is selected by environment variables (`REPOSITORY_PROVIDER`, `LLM_PROVIDER`, etc.). No profile is hard-coded.

## Provider Abstraction Rule

New features must use provider abstractions. Route handlers and business logic must not call GCP or any cloud service directly.

Required provider abstractions:
- `RepositoryProvider` — tickets, agent runs, artifacts, tasks, requirements
- `ArtifactStore` — file/blob output storage
- `SecretProvider` — API keys and credentials
- `LLMProvider` — text generation (already implemented)
- `ToolRunner` — external tool invocation (implemented, Release 5)
- `ObservabilityProvider` — logging, tracing, cost records

Current Firestore and Cloud Run support is the cloud-profile implementation of `RepositoryProvider`. It is optional, not required.

Memory repository is acceptable for tests and local dev. Real local mode should eventually use durable local storage (SQLite or local Postgres) — not in scope for current tasks.

Task 25 check definitions and check runs must use the repository abstraction and must not assume Firestore.

## Work-Safe Rules

Always preserve:

- human approval for risky transitions
- no direct merge without approval
- no direct deploy without approval
- no uncontrolled agent execution
- no secrets in logs or prompts
- repo safety profiles before code automation
- audit trail for agent/tool/human actions
- work-safe mode for workplace use

## Repository Guidance

Do not restructure the repository unless explicitly instructed.

Expected major areas:

- `services/api` — FastAPI backend
- `apps/web` — frontend
- `infra/terraform` — GCP infrastructure
- `docs` — architecture, roadmap, tooling, QA/STLC, and Studio docs
- `.github/workflows` — CI/CD

## Task Execution Protocol

For every task:

1. Read this file.
2. Run `git status`.
3. Inspect only the files relevant to the task.
4. Produce a short plan first.
5. Wait for approval in plan mode.
6. Implement only the approved scope.
7. Add or update tests when behavior changes.
8. Run relevant tests/builds.
9. Fix only relevant failures.
10. Summarize the diff.

## Plan Format

When planning, return:

1. Current repo observations
2. Files to create/change
3. Implementation steps
4. Tests to add/update
5. Commands to run
6. Out of scope
7. Risks/assumptions

## Summary Format

After implementation, return:

Summary:

- ...

Tests:

- ...

Files changed:

- ...

Risks / assumptions:

- ...

Next step:

- ...

## Current Out of Scope Unless Explicitly Requested

Do not implement these unless the current task explicitly asks for them:

- GitHub App / webhook integration
- Live monitoring integration (Sentry, Datadog, Cloud Logging polling, OpenTelemetry)
- Auto-remediation, autonomous deploy, autonomous rollback
- Slack / email / PagerDuty notifications
- evaluator/multi-candidate orchestration
- MCP server
- Temporal / Kestra / LangGraph
- vector DB/RAG
- billing/multi-tenancy
- ForgeLoop Studio modules (ProductScout, AuditLens, LaunchPilot)
- marketing workflows
- Hardcoding cloud services in route handlers or business logic
- Adding GCP dependencies to new features without a provider abstraction

## Detailed Docs

Use these only when relevant:

- `docs/architecture.md` — current and target architecture
- `docs/roadmap.md` — release roadmap
- `docs/tooling-strategy.md` — open-source tools to reuse
- `docs/qa-strategy.md` — QA/STLC pipeline direction
- `docs/forge-loop-studio.md` — future Studio vision

## GitHub Push Rule

After each completed task, if tests/builds pass:

1. Run `git status`.
2. Summarize changed files.
3. Commit changes with a clear task-based commit message.
4. Push to the current remote branch.
5. Report:
   - branch name
   - commit hash
   - pushed remote
   - tests/builds run

Do not commit or push if:

- tests fail
- build fails
- secrets are present
- unrelated files are changed
- the user has not approved the task implementation

## Cost & Safety Policy (Tasks 75–100) — Enforced

This policy is binding. It supersedes any older "always out of scope"
phrasing: the direction is **controlled adoption, not endless
expansion**. Authoritative direction lives in `docs/roadmap.md` and
`docs/architecture.md`.

1. **Plan mode first.** Non-trivial work: inspect, produce a short plan,
   then implement the approved scope only. No large unplanned
   implementation.
2. **No scope expansion.** The post-32 roadmap is bounded to Tasks
   75–85 (controlled adoption, complete) and Release 10 — Operational
   Execution Layer, Tasks 86–100 (authorized by Task 86). Do not start
   work beyond 100, and do not re-expand a "deferred" item, without an
   explicit `docs/roadmap.md` update. Release 10 wires existing
   foundations into real execution and adds only the optional,
   config-gated Phase-B adapters and the controlled draft-PR path
   scoped in Tasks 86–100.
3. **No paid/expensive services without approval.** Default to free /
   local-first (Ollama local, DeepSeek default hosted). Prometheus/
   OpenTelemetry/Grafana stay free/local; no paid monitoring.
4. **No Kimi unless explicitly approved.** Kimi is an expensive,
   approval-gated fallback only; the budget guard is fail-closed. Never
   make Kimi a default route.
5. **Runner discipline.** Lightweight/deterministic runner by default;
   OpenHands only for broad/complex, human-approved work.
6. **No deploy/merge automation without approval.** Auto-remediation is
   advisory only. Per the **Task 99 Controlled Branch/PR Automation
   Policy** (see `docs/roadmap.md`), controlled automation is *allowed*
   only within a strict envelope: create a fresh `forgeloop/*` branch
   off a non-protected base, local commit of human-approved runner
   output, push that branch, and open a **draft** PR — each
   config-gated (flags default false), approval-gated, and
   QA/check-gated, fully audited. Always forbidden: merge, auto-ready,
   deploy/release, force-push, protected-branch push/branch/target,
   ruleset mutation, destructive git, auto-review. Human approval
   precedes any executable DevTask.
7. **Infra is sequenced, not sprawled.** Valkey → NATS → Temporal;
   K3s optional spike only; Pub/Sub-Eventarc a later cloud adapter;
   Kafka deferred. New infra requires a provider abstraction and must
   never be the source of truth.
8. **RAG stays controlled.** Project-memory/summary retrieval only, off
   by default; never broad raw-code/log/secret indexing.
9. **GitHub push after a completed task** only if tests/builds pass and
   the user has configured/confirmed it (see the GitHub Push Rule).
10. Preserve all historical release/task summaries — never delete them.
