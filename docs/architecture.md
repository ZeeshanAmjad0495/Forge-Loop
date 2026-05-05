# Architecture

## MVP overview

IncidentPilot is a human-supervised product engineering control plane. The current implementation (Releases 1 + 2) accepts software tickets and generates implementation-ready planning briefs using a user-selectable LLM provider. All output is for human review — the system does not create branches, open pull requests, or make any autonomous production changes.

Releases 3–6 (planned, not implemented) extend this to a project-centered model with project memory, tool-runner-driven code execution, AI-assisted PR review, and incident triage. See [Target architecture](#target-architecture-releases-36) below.

## System diagram

```
Browser (React + Vite)
       │
       │  HTTP (fetch)
       ▼
Cloud Run — FastAPI
       │               │
       ▼               ▼
  Firestore       DeepSeek API
  (persistence)   (LLM provider)
```

Local development replaces Firestore with in-memory repositories and DeepSeek with the mock provider — no GCP credentials required.

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
| Local dev | InMemory (default) | Not used |
| Automated tests | InMemory (always) | Never called |
| Cloud Run | Firestore | `tickets`, `agent_runs`, `artifacts` collections |

Switching is controlled by `REPOSITORY_PROVIDER=memory|firestore`. The InMemory repository holds state in a plain dict — it resets on process restart and is not suitable for production.

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

## Human-supervised design

All agent output is markdown text for human review. The system generates briefs; humans decide whether and how to act on them. No autonomous code edits, branch creation, PR opens, merges, or deployments are performed. Human approval points are explicitly listed in every generated brief.

---

## Current boundaries (not in current implementation)

Planned items are listed with their target release. Always-out items will not be added inside the 32-task roadmap.

| Capability | Status |
|------------|--------|
| Project context / Project Memory | Planned, Release 4 |
| GitHub App / webhook integration | Planned, Release 3 |
| Branch / PR creation | Planned, Release 3 |
| Approval gate workflow / audit log | Planned, Release 3 |
| Tool runner abstraction (OpenHands, Aider, …) | Planned, Release 4 |
| Dev task decomposition / multi-candidate orchestration | Planned, Release 4 |
| AI-assisted PR review | Planned, Release 5 |
| CI failure analysis / test run evaluation | Planned, Release 5 |
| Prompt version tracking | Planned, Release 5 |
| Incident triage / production failure analysis | Planned, Release 6 |
| Marketing / product-growth | Parked, Release 7 (not in active roadmap) |
| Slack or email notifications | Always out (current roadmap) |
| Authentication, RBAC, multi-tenancy, billing | Always out (current roadmap) |
| Frontend deployment / hosting | Always out (current roadmap) |
| Pub/Sub or Eventarc triggers | Always out (current roadmap) |
| Vector search / RAG / MCP server | Always out (current roadmap) |
| Multi-environment Terraform workspaces | Always out (current roadmap) |

---

## Target architecture (Releases 3–6)

IncidentPilot's long-term role is **control plane**, not coding agent. This section describes the intended architecture for Releases 3–6. **Nothing here is implemented yet.** The active engineering scope is fixed at 32 tasks across 6 releases — see [README → Future roadmap](../README.md#future-roadmap) for the per-release breakdown.

### Control-plane principle

IncidentPilot owns:

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

### Project Memory (planned, Release 4)

Per-project storage that gives planning agents the context they need to produce a useful brief without re-explaining the codebase each time. Stores: architecture decisions, tech stack, domain rules, important files, coding standards, testing/deployment commands, previous feedback, approved/rejected approaches, known risks, common failure patterns, prompt versions, and other project-specific context. Project memory is owned by IncidentPilot, not the LLM.

### Tool Runner abstraction (planned, Release 4)

A single interface for invoking external coding tools. Conceptual shape:

```
ToolRunner.invoke(task, project_context) → ToolRunResult
```

First targets: OpenHands, Aider. Later: Cline, OpenCode, Hermes Agent, OpenClaw (if useful). IncidentPilot tracks each tool run as an AgentRun, stores its output as an Artifact, and surfaces results to humans for approval. It does not reimplement what these tools already do.

### Orchestrator / Evaluator pattern (planned, Releases 4–5)

Each workflow stage may run multiple agent candidates in parallel. An evaluator scores the outputs and selects the best before proceeding to the next stage. A human approves or requests changes. Applies to:

- Planning briefs — multiple LLM candidates → evaluated → selected
- Dev task outputs — multiple coding-tool attempts → tested → selected
- PR content — generated → AI-reviewed → human-reviewed → merged

May be implemented later via Kimi swarm capabilities, a parallel AgentRun abstraction, or LangGraph if a real need appears.

### Human approval gates (planned, Release 3)

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

### Audit trail (planned, Release 3)

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

Not part of the active 32-task roadmap. Plan separately after Release 6 is complete. Possible future scope: product brief generator, landing page copy, marketing campaign planner, social post generator, cold outreach drafts, user feedback collector, competitor/research tracker.
