# Architecture

## Implementation status

**Releases 1–6 are complete (all 32 tasks).** ForgeLoop is a human-supervised autonomous SDLC + STLC control plane. All output is for human review — the system does not create branches, open pull requests, or make any autonomous production changes.

Implemented capabilities include: ticket creation, planning agent, LLM provider selection, admin auth/login, project context and project memory, structured requirements intake, task/subtask decomposition, human approval gates, audit events, repo connection and safety profiles, deterministic QA check definitions and check runs, Langfuse tracing, ToolRunner abstraction and OpenHandsRunner (dry-run foundation), PR draft workflow (metadata-only, no GitHub API), Kody/Kodus PR review tracking (no external calls), CI failure ingestion and advisory analysis, production incident workflow and advisory triage, and project memory learning loop (human-supervised candidate flow).

Future work (Release 7 / Execution Bridge / ForgeLoop Studio) is out of scope. See [ForgeLoop Studio](#forgeloop-studio-future-vision) and [Active build boundary](#active-build-boundary).

## Local-first / cloud-optional

ForgeLoop is **cloud-supported, not cloud-dependent**. The same codebase runs locally with zero GCP dependencies:

| Default | Verified behavior |
|---|---|
| `REPOSITORY_PROVIDER=memory` | In-memory repositories — no Firestore, no GCP credentials required |
| `REPOSITORY_PROVIDER=local_document` | MongoDB-backed repositories for durable single-developer local runs (Task 40A); `pymongo` is imported lazily |
| `LLM_PROVIDER=mock` | Mock LLM — no external API calls, no keys required |
| `AUTH_ENABLED=true` | Auth enabled by default; local dev should set `AUTH_TOKEN_SECRET` or disable with `AUTH_ENABLED=false` |
| `OPENHANDS_EXECUTION_ENABLED=false` | OpenHands dry-run only — no subprocess or network execution |
| Kody review | Tracking adapter only — no external Kody API calls |
| GitHub | No GitHub API calls anywhere in the current codebase |

Firestore is imported lazily inside the `get_repositories()` factory branch — only resolved when `REPOSITORY_PROVIDER=firestore`. All automated tests run against in-memory repositories and the mock LLM provider. Cloud is optional, not required.

Profile is selected by environment variables. No profile is hard-coded.

## System diagrams

### Local profile (no GCP required)

```
Browser (React + Vite)
       │  HTTP (fetch)
       ▼
localhost — FastAPI
       │               │
       ▼               ▼
  InMemory repos   Mock / Ollama /
  (or SQLite,      DeepSeek / Kimi
   future)         as configured
```

### Cloud profile

```
Browser (React + Vite)
       │  HTTP (fetch)
       ▼
Cloud Run — FastAPI
       │               │
       ▼               ▼
  Firestore       DeepSeek / Kimi /
  (persistence)   hosted LLM provider
```

---

## Core entities

### Ticket

Represents a user story, bug report, or work request.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (UUID) | |
| `title` | string | |
| `description` | string | |
| `status` | `created` \| `brief_generated` | |
| `created_at` | datetime (UTC) | |
| `updated_at` | datetime (UTC) | |

### AgentRun

Records one execution of an agent against a ticket.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (UUID) | |
| `ticket_id` | string | Foreign key to Ticket |
| `agent_type` | `planning` | Only type in MVP |
| `provider` | string | e.g. `mock`, `deepseek` |
| `model` | string | e.g. `deepseek-chat` |
| `status` | `pending` \| `running` \| `completed` \| `failed` | |
| `started_at` | datetime (UTC) | |
| `completed_at` | datetime (UTC) \| null | |
| `error_message` | string \| null | Set on failure |

### Artifact

Stores the output produced by an agent run.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (UUID) | |
| `ticket_id` | string | |
| `agent_run_id` | string | |
| `artifact_type` | `implementation_brief` | Only type in MVP |
| `content` | string (markdown) | |
| `created_at` | datetime (UTC) | |

### LLMProvider

A protocol (interface) implemented by each provider.

| Attribute / method | Description |
|--------------------|-------------|
| `provider_name: str` | e.g. `"mock"`, `"deepseek"` |
| `model_name: str` | Model identifier |
| `generate_text(prompt: str) → str` | Calls the LLM and returns the response |

---

## Data flow

```
POST /tickets/{id}/planning-runs
  1. Fetch Ticket from repository
  2. Create AgentRun (status=running)
  3. Build prompt from ticket title + description
  4. LLMProvider.generate_text(prompt) → markdown
  5. Store Artifact (artifact_type=implementation_brief)
  6. Update AgentRun (status=completed, completed_at=now)
  7. Update Ticket (status=brief_generated)
  8. Return PlanningRunResponse { agent_run, artifact }
```

On LLM failure:
- AgentRun is updated to `status=failed, error_message=...`
- API returns a 500-level error
- No partial artifact is stored

---

## Backend components

```
services/api/app/
├── main.py           FastAPI app, CORS middleware, route handlers
├── config.py         Env-var config (all settings read at import time)
├── models.py         Pydantic models: Ticket, AgentRun, Artifact, PlanningRunResponse
├── repositories.py   Repository protocol + InMemory + Firestore implementations + factory
├── planning_agent.py Orchestrates AgentRun creation, LLM call, Artifact storage
└── llm/
    ├── base.py       LLMProvider protocol + ProviderError exception
    ├── mock.py       MockLLMProvider — returns hardcoded markdown
    └── deepseek.py   DeepSeekProvider — uses openai SDK with DeepSeek base URL
```

**Repository factory** (`get_repositories()`): reads `REPOSITORY_PROVIDER` env var at call time and returns either InMemory or Firestore repositories. The Firestore client is imported inside the factory so unit tests never trigger GCP credential resolution.

**LLM provider factory** (`get_provider()`): reads `LLM_PROVIDER` env var and returns the appropriate provider instance.

---

## Frontend components

```
apps/web/src/
├── main.tsx    React mount point (StrictMode)
├── App.tsx     Single-component state machine — drives the entire UI
├── api.ts      fetch wrappers: createTicket(), createPlanningRun()
├── types.ts    TypeScript interfaces mirroring backend Pydantic models
└── App.css     Minimal styles (no framework)
```

**UI state machine phases:**

```
idle → creating → created → generating → done
                                      ↘ error
```

The frontend makes no assumptions about the backend's LLM provider or storage backend.

---

## Persistence strategy

| Context | Repository | Firestore |
|---------|-----------|-----------|
| Local dev / local profile | InMemory (default); SQLite/local Postgres planned | Not used |
| Automated tests | InMemory (always) | Never called |
| Cloud profile | Firestore | `tickets`, `agent_runs`, `artifacts` collections |

Switching is controlled by `REPOSITORY_PROVIDER=memory|firestore`. The InMemory repository holds state in a plain dict — it resets on process restart and is not suitable for production.

---

## Runtime profiles

| Profile | Backend | Storage | LLM | Secrets | GCP |
|---------|---------|---------|-----|---------|-----|
| local | FastAPI on localhost | InMemory → SQLite/local Postgres (future) | Mock / Ollama / DeepSeek / Kimi | env vars | Not required |
| hybrid | FastAPI on localhost | Local storage | Hosted LLM if configured | env vars | Not required (GitHub optional) |
| cloud | Cloud Run | Firestore | Any configured provider | Secret Manager | Required |

No profile is hard-coded. Local is the default for personal and product work. Cloud is optional for remote/demo/work deployment.

---

## Provider strategy

| Setting | Provider | Key required |
|---------|----------|-------------|
| `LLM_PROVIDER=mock` (default) | MockLLMProvider | No |
| `LLM_PROVIDER=deepseek` | DeepSeekProvider | Yes (`DEEPSEEK_API_KEY`) |
| `LLM_PROVIDER=kimi` | KimiProvider (Moonshot) | Yes (`KIMI_API_KEY`) |
| Gemini, Vertex AI, Claude | Not implemented | — |

`LLM_PROVIDER` sets the **default** provider. Per-request override is supported via the `provider` field on `POST /tickets/{ticket_id}/planning-runs`. `GET /llm/providers` exposes the list of providers and whether each is configured (without leaking keys).

**Task 87 — enforced routed execution.** Every real LLM call resolves its provider through the ModelRouter via `services.model_routing.resolve_routed_provider` (the single enforced entrypoint; routes use `routes.common.resolve_routed_provider_or_400`). Routes/services never call the provider factory directly — only `llm/__init__.py` (factory internals) and the informational `GET /llm/providers` may name a concrete provider. A per-request `provider` override is still honored, but an expensive (Kimi) override is gated by the same approval/budget policy as automatic routing — it can no longer bypass the guard. When `LLM_PROVIDER=mock` (local/test profile, no keys) routing honors mock. `MODEL_ROUTING_ENFORCED` (default true) is an emergency escape hatch to the legacy path. A structural test asserts no route/service module selects a provider directly.

**Task 88 — CostRecord + BudgetGuard wired into routed execution.** The same chokepoint runs the provider BudgetGuard (`provider_budget.check_provider_allowed`) and persists a `planned` (or `blocked`) `CostRecord` for every real routed call — provider, model, routing reason, fallback chain, project. An expensive/over-budget/unapproved provider is rerouted to the normal reasoning provider and a zero-cost `blocked` record is written (mirrors the model-route preview endpoint; persistence failures are swallowed and never break a workflow). Token usage is recorded as explicitly unavailable — DeepSeek/Kimi providers do not surface per-call usage yet, so records are `planned` at resolution time; actual-token reconciliation is future work. A single per-request knob `expensive_approved` (on the LLM-execution request bodies / a query param on the generate routes) authorizes the expensive provider at both the route decision and the BudgetGuard; default `false` keeps Kimi blocked unless `KIMI_AUTO_FALLBACK_ENABLED` or `KIMI_REQUIRE_APPROVAL=false`. The mock no-provider profile and the enforcement-disabled escape hatch do not record cost.

**Task 89 — ContextPack enforced across model-facing workflows.** The same chokepoint also builds, persists, and links a compact `ContextPack` before every real model call (`CONTEXTPACK_ENFORCED`, default true). The existing layered builder auto-fills project profile / architecture / quality-rules from project state and reduces them to the token budget; the resulting `context_pack_id` + estimated tokens are linked onto the `ModelRouteDecision` and the cost-record metadata. Oversized raw context (reduction had to drop layers) **warns by default**; `CONTEXTPACK_BLOCK_OVERSIZED=true` makes it a hard 4xx block. Builder failures are swallowed (never break a workflow). The mock no-provider profile and the enforcement-disabled escape hatch skip ContextPack (consistent with the cost-wiring posture). Agents' prompt assembly is unchanged — enforcement is at the chokepoint, not a per-agent rewrite.

The `LLMProvider` protocol in `llm/base.py` makes adding a new provider a matter of creating a new file and registering it in the factory's `_PROVIDER_REGISTRY` — no changes to `planning_agent.py` or the API routes.

---

## GCP infrastructure (Terraform)

All resources are defined in `infra/terraform/`. Terraform manages infrastructure; it does not run in CI.

| Resource | Purpose |
|----------|---------|
| `google_artifact_registry_repository` | Docker image storage |
| `google_cloud_run_v2_service` | Managed serverless backend, scales to zero |
| `google_firestore_database` | Native-mode document database |
| `google_service_account` | Runtime identity for Cloud Run |
| `google_project_iam_member` | `roles/datastore.user` for Firestore access |
| `google_secret_manager_secret` | Holds DeepSeek API key (value added out-of-band) |
| `google_secret_manager_secret_iam_member` | `roles/secretmanager.secretAccessor` on the secret only |

The Cloud Run resource uses `lifecycle { ignore_changes = [image] }` so the deploy workflow can update the image without Terraform reverting it.

---

## Provider abstraction rule

New features must use provider abstractions. Route handlers and business logic must not call GCP or any cloud service directly.

| Abstraction | Current implementations | Planned |
|-------------|------------------------|---------|
| `RepositoryProvider` | InMemory, Firestore, LocalDocument (MongoDB, Task 40A) | SQLite/Postgres (future) |
| `LLMProvider` | Mock, DeepSeek, Kimi | Ollama (local), others |
| `ArtifactStore` | — | Filesystem (local), GCS (cloud) |
| `SecretProvider` | env vars | Secret Manager (cloud) |
| `ToolRunner` | OpenHandsRunner (instruction-package dry-run, Task 27) | OpenHands execution + PR draft workflow (Release 5, gated by `OPENHANDS_EXECUTION_ENABLED`) |
| `ObservabilityProvider` | — | Langfuse, Cloud Logging |

This rule applies to Release 4–6 features. Task 25 check definitions and check runs must use the repository abstraction and must not assume Firestore.

---

## Human-supervised design

All agent output is markdown text for human review. The system generates briefs; humans decide whether and how to act on them. No autonomous code edits, branch creation, PR opens, merges, or deployments are performed. Human approval points are explicitly listed in every generated brief.

---

## Implemented capabilities (Releases 1–6)

All 32 tasks are complete. The table below summarises what is and is not implemented.

| Capability | Status |
|------------|--------|
| Ticket creation and retrieval | **Implemented, Release 1** |
| Planning agent (LLM brief generation) | **Implemented, Release 1** |
| Multi-provider LLM support (Mock, DeepSeek, Kimi) | **Implemented, Release 2** |
| Admin auth / JWT | **Implemented, Release 2** |
| Project context / Project Memory | **Implemented, Release 3** |
| Structured requirements intake | **Implemented, Release 3** |
| Task / subtask decomposition | **Implemented, Release 3** |
| Approval gate workflow / audit log | **Implemented, Release 3** |
| Repo connection + repo safety profile | **Implemented, Release 4** |
| Deterministic QA check definitions and check runs (Semgrep, OSV-Scanner, Trivy, Gitleaks, axe-core, Playwright metadata) | **Implemented, Release 4** |
| Langfuse tracing (prompt versions, cost, token records) | **Implemented, Release 4** |
| ToolRunner abstraction + OpenHandsRunner (dry-run / package foundation) | **Implemented, Release 5** |
| PR draft workflow (metadata-only; no GitHub API calls) | **Implemented, Release 5** |
| Kody/Kodus PR review tracking adapter (no external calls) | **Implemented, Release 5** |
| CI failure ingestion (`CIEvent`) + advisory analysis (`CIAnalysis`) | **Implemented, Release 6** — manual/programmatic ingestion only; no CI provider API calls, no auto-fix |
| Incident ingestion (`Incident`) + advisory triage (`IncidentAnalysis`) | **Implemented, Release 6** — manual/programmatic ingestion only; no monitoring providers, no auto-detection, no auto-remediation |
| Project memory learning loop (`MemoryLearningRun`, `MemoryCandidate`) | **Implemented, Release 6** — human-supervised approve/reject flow; no vector DB, no RAG, no background learning |
| Local workspace metadata + safe directory management (`Workspace`) | **Implemented, Task 33** — Execution Bridge foundation; pathlib-only, no shell, no git, no GitHub, no source-file mutation |
| Safe command runner foundation (`CommandDefinition`, `CommandRun`) | **Implemented, Task 34** — disabled by default; workspace-scoped, allowlist+blocklist, `shell=False`, timeout + output cap, audited; no git, no OpenHands, no Docker |
| Real branch / PR creation via GitHub API | **Not implemented** — belongs to future Execution Bridge |
| Live OpenHands execution | **Not implemented** — belongs to future Execution Bridge |
| Live Kody integration (external API calls) | **Not implemented** — belongs to future Execution Bridge |
| GitHub App / webhook integration | **Not implemented** |
| Live monitoring / auto-detection / auto-remediation | **Not implemented** |
| Multi-candidate orchestration / evaluator | Deferred |
| Vector search / RAG | Always out (current roadmap) |
| Marketing / product-growth (LaunchPilot) | Parked, Release 7 |
| Slack or email notifications | Always out |
| RBAC, multi-tenancy, billing | Always out |
| Pub/Sub, Eventarc, MCP, Temporal, LangGraph | Always out |

---

## Architecture: control plane

ForgeLoop's role is **control plane**, not coding agent. All 32 core tasks (Releases 1–6) are now implemented. This section describes the structural principles. Future enhancements (Execution Bridge, Release 7, ForgeLoop Studio) are documented separately.

### Control-plane principle

ForgeLoop owns:

- Project context and project memory
- Workflow state, task and subtask lifecycle
- Artifact storage and versioning
- Agent run coordination
- Evaluator / candidate selection
- Approval gates and audit trail
- Repo safety profiles and work-safe rules
- Tool runner coordination
- Human review loops

It does **not** own code generation or execution — those are delegated to existing coding tools.

### Project-centered data model

```
Project
  ├── ProjectMemory
  │     ├── Architecture decisions
  │     ├── Tech stack
  │     ├── Domain rules
  │     ├── Important files
  │     ├── Coding standards
  │     ├── Testing commands
  │     ├── Deployment commands
  │     ├── Previous human feedback
  │     ├── Approved / rejected approaches
  │     ├── Known risks / common failure patterns
  │     └── Prompt versions
  ├── Tickets / Requirements
  │     └── Planning AgentRuns (N candidates)
  │           ↓
  │         Evaluator / Orchestrator → Selected Artifact
  │           ↓
  │         Human Approval Gate ──(reject)──→ Change Request Loop
  │           ↓ (approve)
  │         DevTasks
  │           └── Subtasks
  │                 └── ToolRunner (OpenHands / Aider / Cline / OpenCode / Hermes Agent)
  │                       └── Test Run + Evaluation
  │                             └── Branch → PR
  │                                   └── AI Review → Human Review → Revision Loop
  │                                         └── Merge (human-approved)
  │                                               └── Deploy (human-approved)
  └── Monitoring / Incident Triage (Release 6)
```

The current implementation covers: Ticket → Planning → Requirements → DevTasks → ToolRunner (dry-run) → PRDraft (metadata) → Review tracking → CI/Incident ingestion → Memory learning. Branch creation, real execution, and merge remain future Execution Bridge work.

### Project Memory (implemented, Release 3)

Per-project storage that gives planning agents the context they need to produce a useful brief without re-explaining the codebase each time. Stores: architecture decisions, tech stack, domain rules, important files, coding standards, testing/deployment commands, previous feedback, approved/rejected approaches, known risks, common failure patterns, prompt versions, and other project-specific context. Project memory is owned by ForgeLoop, not the LLM.

### Tool Runner abstraction (implemented, Release 5)

A single interface for invoking external coding tools. Implemented shape:

```
ToolRunner.invoke(task, project_context) → ToolRunResult
```

`OpenHandsRunner` is the primary implementation (dry-run / instruction-package foundation; `OPENHANDS_MODE=dry_run`). The abstraction supports future secondary adapters: Aider, Cline, OpenCode, Hermes Agent, OpenClaw. ForgeLoop tracks each tool run as a `ToolRun`, stores output as an `Artifact`, and surfaces results to humans for approval. Real OpenHands execution (live subprocess/API call) belongs to the future Execution Bridge.

### Orchestrator / Evaluator pattern (deferred — after single-runner loop is stable)

Each workflow stage may run multiple agent candidates in parallel. An evaluator scores the outputs and selects the best before proceeding to the next stage. A human approves or requests changes. Applies to:

- Planning briefs — multiple LLM candidates → evaluated → selected
- Dev task outputs — multiple coding-tool attempts → tested → selected
- PR content — generated → AI-reviewed → human-reviewed → merged

May be implemented later via Kimi swarm capabilities, a parallel AgentRun abstraction, or LangGraph if a real need appears.

### Human approval gates (implemented, Release 3)

Explicit human approval is required before the system proceeds at each of these transitions:

- Plan approval (brief reviewed and accepted)
- Dev task approval (task scope confirmed before coding starts)
- Branch and PR creation
- Merge to main
- Deployment to production
- Production remediation actions

### Work-safe mode (implemented, Releases 3–6)

Two operating modes:

- **Personal-product mode** — faster, lighter approvals allowed.
- **Workplace mode** — stricter: sanitized inputs where needed, no proprietary or customer data sent to external LLMs unless explicitly approved, no secrets sent to agents, no direct production changes, all transitions require explicit approval.

Common to both modes: no autonomous merge or deploy, no secret exposure, full audit trail, repo safety profiles (branch protection awareness, no-force-push enforcement), blocked paths, required checks, and a dry-run / preview mode for risky operations.

### Audit trail (implemented, Release 3)

Every agent run, candidate output, evaluation score, human decision, prompt version, and artifact revision is stored and queryable. This makes the system auditable and reversible.

### Work-safe features (folded into Releases 3–6)

These are implementation details of existing tasks — they do not add tasks beyond 32:

- Approval gates per stage transition
- Audit log of all actions and decisions
- Agent output scoring metadata on artifacts
- Change request loop with revision tracking
- Prompt version tracking (which prompt → which artifact)
- Repo safety profile (branch protection, no-force-push)
- Work-safe / dry-run mode before executing risky actions
- Definition-of-done checklist before stage advancement
- GitHub branch protection awareness

### Marketing / product-growth (Release 7, parked)

Not part of the active 32-task roadmap. This release is subsumed by LaunchPilot (a ForgeLoop Studio module). Plan separately after Release 6 is complete. Possible future scope: landing page copy, product positioning, marketing campaign planner, social post generator, cold outreach drafts, user feedback collector, competitor/research tracker.

---

## ForgeLoop Studio (future vision)

> **Nothing in this section is implemented.** The active build is ForgeLoop core (Releases 1–6, 32 tasks). ForgeLoop Studio is documented here for architectural awareness only.

ForgeLoop Studio is a future AI-native product factory. ForgeLoop is its core engine. The full suite adds market discovery upstream (ProductScout), independent auditing downstream (AuditLens), and marketing/sales support (LaunchPilot).

### Flow diagram

```
ProductScout
  → Product Brief / Requirements
  → ForgeLoop
       → Planning
       → Task / Subtask Decomposition
       → Coding Tool Runners
       → QA / STLC Pipeline
       → PR / Review Loop
       → Deployment / Maintenance
  → AuditLens
       → Independent Audit
       → Improvement Tickets
       → ForgeLoop
  → LaunchPilot
       → Website / Positioning / Outreach
       → Client Feedback / Custom Requirements
       → ForgeLoop
```

### Module descriptions

**ProductScout** — market research and product discovery bot. Researches markets, competitors, pain points, target users, pricing signals, and product opportunities. Produces structured product briefs and requirements that enter ForgeLoop as tickets.

**ForgeLoop** — this repo. Human-supervised SDLC + STLC control plane. Converts requirements into architecture decisions, planning briefs, dev tasks, code (via tool runners), QA runs, PR/review loops, deployments, maintenance loops, and project memory. All transitions are human-approved.

**AuditLens** — independent third-party style auditor. Audits implemented software for security, compliance, accessibility, UX, performance, test coverage, business logic gaps, and market-readiness. Generates improvement tickets that re-enter ForgeLoop. Can re-audit periodically as market expectations, dependencies, and security risks evolve.

**LaunchPilot** — marketing and sales support bot. Helps create landing pages, product positioning, launch plans, outreach messages, demos, sales material, and client-specific requirement intake. Client feedback and custom requirements return to ForgeLoop as new tickets. Subsumes Release 7 (parked, not in active roadmap).

### Shared data model

These concepts are used across Studio modules. ForgeLoop owns and stores all of them.

| Concept | Owner | Description |
|---------|-------|-------------|
| `Project` | ForgeLoop | All work is project-scoped |
| `ProjectMemory` | ForgeLoop | Architecture decisions, standards, feedback, history |
| `Requirement` | ProductScout → ForgeLoop | Structured input from discovery |
| `Ticket` | ForgeLoop | Unit of work entering the engineering pipeline |
| `Task / Subtask` | ForgeLoop | Decomposed from approved tickets |
| `AgentRun` | ForgeLoop | One execution of an AI agent against a task |
| `Artifact` | ForgeLoop | Agent-generated output (brief, code diff, review notes, etc.) |
| `Evaluation` | ForgeLoop | Score and selection from multi-candidate agent runs |
| `Approval` | Human → ForgeLoop | Explicit human sign-off at gate transitions |
| `AuditEvent` | AuditLens → ForgeLoop | Finding from an independent audit pass |
| `ToolRun` | ForgeLoop | External coding-tool invocation record (OpenHands, Aider, etc.) |
| `PullRequestDraft` | ForgeLoop | Metadata-only PR draft: generated title/body, source/target branch, status machine, optional external URL. Created by `POST /projects/{id}/pr-drafts`, approved by `POST /pr-drafts/{id}/approve`. No GitHub API call. |
| `CostRecord` | ForgeLoop | Token usage and compute cost per agent run |

### Active build boundary

**Releases 1–6 are complete (all 32 tasks).** The implemented core includes everything from ticket creation through project memory learning. The post-32 controlled-adoption work (Tasks 75–85) is also complete. The **currently authorized active scope is Release 10 — Operational Execution Layer (Tasks 86–100)**, authorized by Task 86 via an explicit [`roadmap.md`](roadmap.md) update. Release 10 wires the already-built cost/router/context/runner/observability foundations into real execution, adds optional config-gated Phase-B infra adapters (Temporal/NATS/Valkey, DB remains source of truth), and a controlled draft-PR path (never merge/deploy). It is **controlled adoption**, not endless expansion — bounded to Tasks 86–100; no work beyond 100 without a further explicit roadmap update. ForgeLoop Studio (ProductScout, AuditLens, LaunchPilot) and live Kody/GitHub-merge/deploy automation remain **deferred** (not "always out of scope"): adopted later only via explicit roadmap update, never by silent scope creep. The `docs/release-8…release-12-*-summary.md` files (including `release-10-evaluation-lab-summary.md`, old Tasks 57–62) are historical exploratory artifacts, **not** the authoritative scheme, and unrelated to this Release 10; they are preserved, never deleted.

### Controlled adoption & cost-safe policy (Tasks 75–100)

The maintained direction (this file + `roadmap.md` + the repo `CLAUDE.md`) is authoritative; older "always out of scope" phrasing elsewhere is superseded by **deferred / controlled adoption**.

- **Cost-safe model routing:** Ollama for local cheap workflows; DeepSeek as the default hosted reasoning provider; **Kimi is an expensive, approval-gated fallback only** (budget guard fail-closed). See the Task 75/76 sections.
- **Runner strategy:** deterministic/lightweight runner by default; **OpenHands only for broad/complex, human-approved work** (Task 77). **Task 90 makes the RunnerRouter mandatory** for real coding execution: `OpenHandsExecutionService`/`AiderExecutionService` (`local` mode) call `runner_router.enforce_runner_route` and record the decision (`runner_route_decided` audit event). The router never auto-selects OpenHands for narrow tasks; a direct OpenHands request the router would route elsewhere is blocked unless the run is human-approved (the approval is the documented broad/complex justification; the override is recorded). A `deterministic` selection blocks any code-execution request; Aider stays a valid lightweight runner (blocked only on `deterministic`). `RUNNER_ROUTER_ENFORCED` (default true) is an emergency escape hatch. **Task 91** force-wires runner locks + workspace isolation: real (`local`) OpenHands/Aider execution acquires a non-blocking per-dev-task lock (`task_execution_lock`, 409 `TASK_BUSY`) nested around the existing per-workspace lock (409 `WORKSPACE_BUSY`) — blocking the same task running concurrently even across different workspaces; both release on success/failure/timeout. Workspace-root safety (`assert_workspace_safe`) is already re-asserted at runner start (always enforced, even when `WORKSPACE_ALLOW_OUTSIDE_ROOT=true` it still blocks system/credential trees). Locks are in-process (single-worker deployment; reset on restart — a distributed lock is out of scope); project/branch locks are intentionally not added (not needed for the hard-sync safety concern; no branch/PR automation yet).
- **Infrastructure sequence:** Valkey first (cache/locks), then NATS (local event bus), then Temporal (durable workflows); **K3s optional spike only**; a Pub/Sub–Eventarc cloud adapter is a later option behind the `EventBus` interface; **Kafka deferred** (Tasks 79–80). **Task 92** adds a DB-backed local background worker: `Job`/`JobAttempt` repositories (memory/Mongo/Firestore — the Job repo is the durable source of truth, *not* the ephemeral Task-80 `WorkflowEngine`), `services/job_worker.py` with attempts/retries/timeout/heartbeat/failure-reason and a handler registry, exposed via `POST /projects/{id}/jobs` + `POST /jobs/worker/run-once`. The worker is **opt-in** (`BACKGROUND_WORKER_ENABLED`, default false) and drains **explicitly** (no daemon thread). One safe job type is wired: `artifact_summary` (deterministic, no external calls). Temporal/NATS/K3s/distributed workers remain out of scope (Tasks 93/94). **Task 93** lands the Temporal Phase-B *seam*: `WORKFLOW_ENGINE_PROVIDER=temporal` now selects a `TemporalWorkflowEngine` that lazily checks for `temporalio` and **falls back to the local DB/in-memory engine** when it (or a server) is absent — no `temporalio` dependency, tests stay offline, no more hard fail-fast. Exactly one workflow is migrated onto the engine abstraction: `incident_to_triage` (best-effort tracking at `incident_analysis_workflow.create_analysis`, `WORKFLOW_ENGINE_TRACKING_ENABLED` default true, failures swallowed). The `IncidentAnalysis` record remains the durable source of truth — the engine is ephemeral orchestration bookkeeping only. Migrating other workflows, a live `temporalio` client/server, and cloud Temporal stay out of scope. **Task 94** lands the symmetric NATS Phase-B seam: `EVENT_BUS_PROVIDER=nats` selects a `NatsEventBus` that lazily checks for `nats` and **falls back to the in-memory bus** when absent (no `nats` dependency, no fail-fast). After every audit event is persisted (the audit log is the source of truth, written first), `audit_writer` does a **best-effort** fan-out publish to the EventBus — gated by `EVENT_BUS_PUBLISH_ENABLED` (**default false**), failures swallowed (never affects the audit write). Mandatory NATS, Kafka, Pub/Sub–Eventarc, event-replay UI, and a live `nats` server stay out of scope.
- **RAG:** controlled project-memory/summary retrieval only — **no broad raw-code/log/secret RAG**; off by default (Task 81).
- **Observability:** free/local-first OpenTelemetry-flag / Prometheus-text / optional Grafana; no paid monitoring (Task 82).
- **Auto-remediation:** advisory only — no merge/deploy/branch/PR automation; human approval before any DevTask (Task 83).
- **Release 10 — Operational Execution Layer (Tasks 86–100):** makes the Task 75–85 foundations operational — ModelRouter enforced everywhere, CostRecord/BudgetGuard force-wired, ContextPack required, RunnerRouter mandatory, runner locks/workspace isolation, DB-backed local worker, optional config-gated Temporal/NATS/Valkey Phase-B adapters (DB stays source of truth), real free metrics, CLI-first layer, dashboard timeline, and a controlled draft-PR path (Task 99 policy → Task 100 implementation; never merge/deploy/force-push).
- **Bounded roadmap:** Tasks 75–85 (complete) plus Release 10 (Tasks 86–100) are the post-32 scope. No task beyond 100 without an explicit `roadmap.md` update.

### Durable workflow + event foundation (Task 80)

ForgeLoop is local-first; long-running, human-supervised agent work needs durable workflows and event fanout without a heavy infra migration. Two provider abstractions back this:

- **`EventBus`** (`services/event_bus.py`) — `publish` / `subscribe`. Default `InMemoryEventBus` (synchronous, dependency-free, deterministic). Notification channel only; **never the source of truth**.
- **`WorkflowEngine`** (`services/workflow_engine.py`) — `start_workflow` / `signal_workflow` / `get_workflow_status` / `cancel_workflow`. Default `InMemoryWorkflowEngine`. Human approval is an **explicit signal** (`human_approval`), never an implicit timeout. Ephemeral orchestration bookkeeping only — durable effects (tickets, tasks, approvals, artifacts, audit) stay in the existing repositories/audit events.

Phasing:

- **Phase A (implemented):** interfaces + in-memory implementations + config + tests + `GET /runtime/workflow`. No external infra; defaults stay test-friendly.
- **Phase B (deferred):** NATS adapter for `EventBus`, Temporal adapter for `WorkflowEngine`, behind `EVENT_BUS_PROVIDER=nats` / `WORKFLOW_ENGINE_PROVIDER=temporal`. Selecting these today fails fast with guidance (no `nats`/`temporalio` import). A GCP Pub/Sub–Eventarc adapter is a later cloud option behind the same `EventBus` interface. Kafka is intentionally **not** adopted (NATS is sufficient for ForgeLoop's fanout).
- **Phase C (deferred):** migrate **one** low-risk candidate workflow (catalog: `requirement_to_plan`, `plan_to_dev_tasks`, `approved_dev_task_to_runner`, `runner_result_to_pr_draft`, `ci_failure_to_analysis`, `incident_to_triage`, `remediation_draft_to_approved_task`) onto the engine. No bulk migration.

**K3s** is an *optional spike only* — consider it later only if isolated per-task worker execution is required (untrusted multi-file runner sandboxing at scale). It is **not** a default runtime and the K3s runner is not implemented unless explicitly approved.

### Controlled project-memory retrieval (Task 81)

Project history grows; ForgeLoop adds *narrow* semantic recall — **not** broad RAG. `VectorStore` (`services/vector_store.py`) indexes **summarized** knowledge only: project memory candidates, approved project memory, artifact summaries, architecture decisions, prior human feedback, and incident/CI lessons. Raw repo/code/logs/secrets/binaries are **never** indexed (hard refusal in `index()`).

- **Provider:** the smallest local-first option — a dependency-free, deterministic in-memory term-frequency cosine store. No embeddings API, no paid provider, no external vector DB; tests stay deterministic and offline. `chroma` / `qdrant` / `pgvector` are the recommended future local adapters (selecting them fails fast with guidance, no import — same pattern as Tasks 79/80).
- **Disabled by default** (`VECTOR_RETRIEVAL_ENABLED=false`). ContextPack calls retrieval only when enabled **and** the request opts in (`use_retrieval`), as an additive enrichment that never alters the budgeted layers.
- **Bounded** by `VECTOR_TOP_K` (count) and `VECTOR_MAX_CHUNK_TOKENS` (per-chunk), project-scoped, and every match carries citations (`source_id`/`kind`). Never the source of truth.

### Free observability (Task 82)

`services/metrics.py` is a dependency-free, in-process metrics registry exposed in Prometheus text format at `GET /metrics` (auth-required; 404 when disabled). No client library, no OpenTelemetry import (OTEL is a config flag only — heavy dependency, deferred), no paid monitoring, no Cloud Logging polling, no alert routing. All instrumentation is a no-op unless `OBSERVABILITY_ENABLED` and `METRICS_ENABLED`, so chokepoint hooks never change behavior.

Signals: `llm_route_decision_total`, `provider_call_total`, `provider_call_failed_total`, `provider_estimated_cost_usd_total`, `kimi_blocked_total` (all from the central `record_cost` chokepoint), `runner_selected_total`, `contextpack_tokens_before/after_total`, `workflow_started_total`, `approval_wait_seconds`. `runner_duration_seconds` / `workflow_failed_total` are registered with helpers but emitted by callers (not force-wired into hardened execution paths — same conservative stance as the Task 79 runner-lock). Structured JSON event logs (`STRUCTURED_LOGS_ENABLED`) cover provider/workflow failures. Metrics are aggregate only — never secrets/tokens/prompts/PII, never the source of truth. An optional local Prometheus ships behind the `observability` compose profile (`prometheus.yml`); Grafana dashboards are intentionally out of scope.

### Advisory-only auto-remediation (Task 83)

`services/auto_remediation.py` turns a **completed** CI-failure analysis, incident analysis, or a PR-review's findings into a persisted `RemediationProposal` draft (`source_type`, `source_id`, `severity`, `suspected_root_cause`, `proposed_change`, `risk`, `tests_to_run`, `rollback_note`, `approval_status`). It is **advisory only** and **off by default** (`AUTO_REMEDIATION_ENABLED=false`):

- A proposal never auto-creates work. `POST /remediation-proposals/{id}/approve` creates a `DevTask` **only** when an approved `Approval` row exists for target `("remediation_proposal", id)` — the same human gate pattern as `RevisionWorkItem`. The DevTask then follows the normal runner/PR gates.
- ForgeLoop never auto-merges, auto-deploys, creates branches/PRs, or runs destructive commands from remediation. `AUTO_REMEDIATION_ADVISORY_ONLY=true` forbids the branch/PR allow-flags and is enforced at startup (`validate_startup_config`). There are no auto-merge/auto-deploy flags.
- Routes: `POST /ci-analyses/{id}/propose-remediation`, `POST /incident-analyses/{id}/propose-remediation`, `POST /pr-reviews/{id}/propose-remediation`, `/remediation-proposals/{id}/approve|reject`, plus reads and `GET /runtime/auto-remediation`. `ApprovalTargetType` gained `remediation_proposal`; audit actions `remediation_proposal_created|approved|rejected`.
