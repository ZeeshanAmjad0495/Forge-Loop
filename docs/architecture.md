# Architecture

## MVP overview

ForgeLoop is a human-supervised autonomous SDLC + STLC control plane. The current implementation (Releases 1 + 2) accepts software tickets and generates implementation-ready planning briefs using a user-selectable LLM provider. All output is for human review — the system does not create branches, open pull requests, or make any autonomous production changes.

Releases 3–6 (planned, not implemented) extend this to a project-centered model with project memory, tool-runner-driven code execution, AI-assisted PR review, and incident triage. See [Target architecture](#target-architecture-releases-36) below.

## System diagrams

ForgeLoop is **cloud-supported, not cloud-dependent**. Profile is selected by environment variables.

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
| `RepositoryProvider` | InMemory, Firestore | SQLite (local profile, future) |
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

## Current boundaries (not in current implementation)

Planned items are listed with their target release. Always-out items will not be added inside the 32-task roadmap.

| Capability | Status |
|------------|--------|
| Project context / Project Memory | **Implemented, Release 3** |
| Structured requirements intake | **Implemented, Release 3** |
| Task / subtask decomposition | **Implemented, Release 3** |
| Approval gate workflow / audit log | **Implemented, Release 3** |
| Repo connection + repo safety profile | Planned, Release 4 |
| Deterministic QA/security bundle (Semgrep, OSV-Scanner, Trivy, Gitleaks, axe-core) | Planned, Release 4 |
| Playwright / browser QA lane | Planned, Release 4 |
| Langfuse tracing (prompt versions, cost, token records) | Planned, Release 4 |
| Tool runner abstraction (OpenHandsRunner primary) | Planned, Release 5 |
| PR draft workflow | Planned, Release 5 |
| Branch / PR creation | Planned, Release 5 |
| AI-assisted PR review (Kodus/Kody) | Planned, Release 5 |
| CI failure analysis / ingestion | Planned, Release 6 |
| Incident triage / production failure analysis | Planned, Release 6 |
| Project memory learning loop | Planned, Release 6 |
| GitHub App / webhook integration | Planned, Release 4 (repo connection, narrower scope) |
| Multi-candidate orchestration / evaluator | Deferred (after single-runner loop is stable) |
| Vector search / RAG | Always out (current roadmap) |
| Marketing / product-growth | Parked, Release 7 (not in active roadmap) |
| Slack or email notifications | Always out (current roadmap) |
| Authentication, RBAC, multi-tenancy, billing | Always out (current roadmap) |
| Frontend deployment / hosting | Always out (current roadmap) |
| Pub/Sub or Eventarc triggers | Always out (current roadmap) |
| MCP server | Always out (current roadmap) |
| Temporal, Kestra, LangGraph | Always out unless a specific need appears |
| Multi-environment Terraform workspaces | Always out (current roadmap) |

---

## Target architecture (Releases 4–6)

ForgeLoop's long-term role is **control plane**, not coding agent. This section describes the intended architecture for Releases 4–6. Release 3 (requirements, task decomposition, approval gates, audit events, project memory) is now implemented. The active engineering scope is fixed at 32 tasks across 6 releases — see [README → Future roadmap](../README.md#future-roadmap) for the per-release breakdown.

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

The MVP implements only the leftmost path (Ticket → PlanningAgentRun → Artifact). Project, ProjectMemory, DevTasks, ToolRunner, and the Review/Merge loop are all planned future work.

### Project Memory (implemented, Release 3)

Per-project storage that gives planning agents the context they need to produce a useful brief without re-explaining the codebase each time. Stores: architecture decisions, tech stack, domain rules, important files, coding standards, testing/deployment commands, previous feedback, approved/rejected approaches, known risks, common failure patterns, prompt versions, and other project-specific context. Project memory is owned by ForgeLoop, not the LLM.

### Tool Runner abstraction (planned, Release 5)

A single interface for invoking external coding tools. Conceptual shape:

```
ToolRunner.invoke(task, project_context) → ToolRunResult
```

Primary target: OpenHands (first and only runner until the full loop is validated). Later secondary adapters: Aider (local/manual fallback), Cline (local/manual fallback), OpenCode, Hermes Agent, OpenClaw. ForgeLoop tracks each tool run as an AgentRun, stores its output as an Artifact, and surfaces results to humans for approval. It does not reimplement what these tools already do.

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

### Work-safe mode (planned, Releases 3–6)

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

The current implementation is **ForgeLoop Releases 1–3** (ticket creation, planning agent, LLM provider selection, auth, project context/memory, structured requirements, task decomposition, task lifecycle, approval gates, audit events). Everything else in this section — including all ForgeLoop Studio modules — is future architecture only.
