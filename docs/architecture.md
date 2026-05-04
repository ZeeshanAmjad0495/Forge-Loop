# Architecture

## MVP overview

IncidentPilot is a human-supervised agentic platform. It accepts software tickets and generates implementation-ready planning briefs using an LLM. All output is for human review — the system does not create branches, open pull requests, or make any autonomous production changes.

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
| Kimi, Gemini, Vertex AI | Not implemented | — |

The `LLMProvider` protocol in `llm/base.py` makes adding a new provider a matter of creating a new file and registering it in the factory — no changes to `planning_agent.py` or the API routes.

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

## Current boundaries (not in MVP)

- PR review or creation
- Incident triage or production analysis
- Branch / task decomposition
- GitHub App or webhook integration
- Slack or email notifications
- Authentication, RBAC, or multi-tenancy
- Frontend deployment / hosting
- Pub/Sub or Eventarc triggers
- Vector search or RAG
- Multi-environment Terraform workspaces

---

## Release 2+ architectural direction

IncidentPilot's long-term role is **control plane**, not coding agent. This section describes the intended architecture for Release 2+ work. Nothing here is implemented yet.

### Control-plane principle

IncidentPilot owns workflow state, task lifecycle, artifact storage, approval gates, and the audit trail. It does not own code generation or execution — those are delegated to existing tools.

### Planned Release 2 workflow

```
Ticket / Requirement
       │
       ▼
PlanningAgent(s) — multiple candidates generated
       │
       ▼
Evaluator / Orchestrator — score and select best output
       │
       ▼
Human Approval Gate ──(reject / request changes)──→ Change Request Loop
       │ (approve)
       ▼
Dev Task Decomposition — brief broken into actionable tasks
       │
       ▼
For each dev task:
  Coding Tool (OpenHands / Cline / Aider / OpenCode)
       │
       ▼
  Test Run + Evaluation
       │
       ▼
  PR Creation → AI Review → Human Review
       │ (approved)
       ▼
  Merge (human-approved) → Deploy (human-approved)
```

### Delegation design

IncidentPilot invokes coding tools via API or CLI and stores their output as artifacts. It tracks status, surfaces results to humans, and enforces approval gates. It does not reimplement code generation.

Tools targeted for delegation (not yet integrated):
- **OpenHands** — autonomous coding agent with sandboxed execution
- **Cline** — VS Code agent with file editing and terminal access
- **Aider** — CLI coding agent with git integration
- **OpenCode** — lightweight LLM-driven code editor

### Audit trail

Every agent run, candidate output, evaluation score, human decision, and artifact version is stored and queryable. This makes the system auditable and reversible.

### Work-safe features (planned)

These are implementation details of Release 2 tasks — not separate tasks:
- Approval gates per stage transition
- Audit log of all actions and decisions
- Agent output scoring metadata on artifacts
- Change request loop with revision tracking
- Prompt version tracking (which prompt → which artifact)
- Repo safety profile (branch protection, no-force-push)
- Work-safe / dry-run mode before executing risky actions
- Definition-of-done checklist before stage advancement
- GitHub branch protection awareness
