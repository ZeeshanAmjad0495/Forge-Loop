# CLAUDE.md

# ForgeLoop — Claude Code Operating Instructions

You are the primary coding agent for this repository.

This project must be completed as a focused MVP within 1–2 weeks. Do not expand scope. Do not add speculative features. Do not build future phases unless explicitly instructed.

## Product Definition

ForgeLoop is a **human-supervised autonomous SDLC + STLC control plane** for building, testing, reviewing, maintaining, and improving software products using project-aware AI agents and existing open-source coding, QA, and review tools.

It orchestrates the full software delivery lifecycle from requirement to production. It accepts requirements, coordinates AI agent runs, tracks artifacts, enforces human approval at defined transition points, and delegates code execution to existing open-source coding tools where practical. It does not rebuild coding agents from scratch and it does not autonomously merge or deploy.

Core responsibilities of ForgeLoop:
- Own project context, project memory, workflow state, task lifecycle, and the artifact store
- Coordinate agent runs and evaluate their outputs
- Enforce human approval at defined transition points
- Delegate code execution to existing open-source coding tools where practical
- Maintain a full audit trail of agent runs, evaluations, and human decisions
- Enforce work-safe rules and repo safety profiles

ForgeLoop is not responsible for:
- Writing production code directly
- Executing terminal commands autonomously
- Merging or deploying without human approval
- Sending proprietary or customer data to external LLMs unless explicitly approved

The MVP is much smaller — see MVP Goal below.

### Project-Centered Model (planned, Releases 3–6)

The future data model is project-centered, not only ticket-centered:

```
Project
  ├── ProjectMemory (architecture decisions, tech stack, domain rules,
  │                  coding standards, testing/deploy commands, prior feedback,
  │                  approved/rejected approaches, known risks, prompt versions)
  ├── Tickets / Requirements
  │     └── Planning AgentRuns (N candidates) → Evaluator → Selected Artifact
  │           → Human Approval → DevTasks
  │                 └── Subtasks → ToolRunner execution
  │                       └── Branch → PR → AI Review → Human Review
  │                             → Revision Loop → Merge
  └── Monitoring / Incident Triage
```

The MVP implements only the leftmost path (Ticket → PlanningAgentRun → Artifact). Project, ProjectMemory, DevTasks, ToolRunner, and the Review/Merge loop are planned for Releases 3–6.

### Delegation Principle

Where practical, code execution is delegated to existing open-source coding tools rather than reimplemented. Target tools (none integrated yet):
- OpenHands
- Hermes Agent
- Cline
- Aider
- OpenCode
- OpenClaw (evaluate if useful)

ForgeLoop invokes these tools via API or CLI and stores their output as artifacts. It tracks status, surfaces results to humans, and enforces approval gates.

### Swarm / Evaluator Pattern (planned, Releases 4–5)

Each workflow stage may run multiple agent candidates in parallel. An evaluator scores the outputs and selects the best before proceeding. A human approves or requests changes. May be implemented later via Kimi swarm capabilities, a parallel AgentRun abstraction, or LangGraph if it proves necessary.

### Work-Safe Principles

The system must always preserve:
- Human approval for risky transitions (plan, merge, deploy, remediation)
- No direct merge without approval
- No production deployment without approval
- No secret exposure to agents or in logs
- No uncontrolled agent execution
- Audit trail for important actions
- Repo safety profiles (branch protection awareness, no-force-push enforcement)
- Blocked paths and required checks
- Work-safe / dry-run mode for risky operations

Two operating modes are planned:
- **Personal-product mode**: Faster, lighter approvals allowed.
- **Workplace mode**: Stricter — sanitized inputs where needed, no proprietary or customer data sent to external LLMs unless explicitly approved, no secrets sent to agents, no direct production changes.

### ForgeLoop Studio (future vision, not in active roadmap)

ForgeLoop (this repo) is the active build. It belongs to a larger future product suite called **ForgeLoop Studio** — documented here for architectural awareness only. Nothing in this section is implemented.

ForgeLoop Studio consists of four modules:

| Module | Role |
|--------|------|
| **ProductScout** | Market research and product discovery bot. Researches markets, competitors, pain points, user needs, and pricing signals. Outputs structured product briefs and requirements that feed into ForgeLoop. |
| **ForgeLoop** | This repo. Human-supervised SDLC + STLC control plane. Converts requirements into planning briefs, tasks, code, QA, PRs, reviews, deployments, and maintenance. |
| **AuditLens** | Independent auditor. Audits implemented software for security, compliance, accessibility, UX, performance, test coverage, and market-readiness. Creates improvement tickets that re-enter ForgeLoop. |
| **LaunchPilot** | Marketing and sales support. Landing pages, positioning, outreach, demos, sales material, client requirement intake. Client feedback returns to ForgeLoop as new tickets. Subsumes Release 7 (parked). |

**Rules for this repo:**
- Do not implement ProductScout, AuditLens, or LaunchPilot without explicit instruction.
- LaunchPilot subsumes marketing/product-growth (Release 7). It is parked and not in the active 32-task roadmap.
- Active implementation continues through the 32-task ForgeLoop core roadmap only.

---

## MVP Goal

The MVP accepts a ticket/user story, creates an agent run, generates an implementation-ready brief using an LLM provider, stores the generated artifact, and exposes everything through an API and minimal UI.

The MVP proves the core workflow:

Ticket
→ AgentRun
→ PlanningAgent
→ ImplementationBrief Artifact
→ Human reads/reviews the brief

## Product Direction — Releases 3–6

The architectural direction for work beyond the current implementation is summarised under "Product Definition" above (Project-Centered Model, Delegation Principle, Swarm/Evaluator Pattern, Work-Safe Principles) and detailed per release in "Approved Milestone Order" below.

The full target architecture diagram lives in [`docs/architecture.md`](docs/architecture.md#target-architecture-releases-36).

Work-safe capabilities (approval gates, audit log, scoring metadata, change request loop, prompt version tracking, repo safety profile, work-safe / dry-run mode, DoD checklist, branch protection awareness) are folded into the existing Releases 3–6 tasks and **do not add tasks beyond 32**.

## Hard MVP Scope (Releases 1 + 2)

Build only these capabilities:

1. FastAPI backend
2. Ticket creation and retrieval
3. AgentRun creation for planning
4. ImplementationBrief artifact generation
5. LLM provider abstraction
6. DeepSeek provider
7. Kimi provider
8. Firestore persistence
9. Minimal frontend
10. Dockerized backend
11. GitHub Actions CI
12. Cloud Run deployment
13. Terraform for minimum GCP infrastructure
14. Per-request provider selection (UI + `GET /llm/providers`)
15. README and architecture documentation aligned with product direction

## Explicitly Out of Scope (until their release)

The items below are out of scope for the current release. Most are planned in Releases 3–6. See "Approved Milestone Order" for which release owns each item. Do not implement any of these ahead of their release.

- Building a coding agent from scratch — use existing tools (OpenHands, Aider, Cline, OpenCode, Hermes Agent) instead → Release 4
- Branch creation → Release 3
- PR creation → Release 3
- AI-assisted PR review → Release 5
- Incident triage agent → Release 6
- Production auto-fixes / remediation → Release 6
- GitHub App or webhook integration → Release 3
- Approval gate workflow / audit log → Release 3
- Tool runner abstraction → Release 4
- Multi-candidate / swarm orchestration → Release 4
- Project memory → Release 4 (or earlier if needed by tool runners)
- Prompt version tracking → Release 5
- CI failure analysis → Release 5
- ProductScout, AuditLens, LaunchPilot — ForgeLoop Studio modules, not in the active 32-task roadmap. LaunchPilot subsumes marketing/product-growth (Release 7, parked). Do not implement any of these without explicit instruction.

Always out of scope for the current 32-task roadmap:

- Pub/Sub or Eventarc
- Kubernetes
- Slack integration
- Authentication, user accounts, or RBAC
- Billing or multi-tenancy
- Complex dashboard
- Background workers
- Vector database or RAG
- MCP server
- LangGraph (only adopt if a real need appears in Release 4–5)
- Long-running agent workflows

If asked to implement any out-of-scope item, state which release owns it (or that it is parked) and ask whether to proceed before implementing anything.

## Tech Stack

Backend:

- Python 3.12
- FastAPI
- Pydantic
- pytest
- Uvicorn
- Firestore
- HTTP client for LLM provider calls

Frontend:

- Minimal React or Next.js
- Simple forms
- Markdown display for generated briefs

Cloud:

- Google Cloud Run
- Firestore
- Artifact Registry
- Secret Manager
- Cloud Logging
- Terraform
- GitHub Actions
- Workload Identity Federation

LLM Providers:

- Provider-agnostic design
- DeepSeek as first real provider
- Kimi optional later
- Gemini optional later
- All providers mocked in automated tests

## Repository Structure

Use this structure:

incidentpilot/
services/
api/
app/
**init**.py
main.py
config.py
models.py
repositories.py
planning_agent.py
llm/
**init**.py
base.py
deepseek.py
tests/
Dockerfile
pyproject.toml
apps/
web/
infra/
terraform/
docs/
sample-ticket.md
architecture.md
.github/
workflows/
api-ci.yml
api-deploy.yml
CLAUDE.md
README.md

Do not restructure this unless explicitly instructed.

## Core Domain Model

The MVP has four core entities.

### Ticket

A ticket represents a user story, bug report, or work request.

Fields:

- id
- title
- description
- status
- created_at
- updated_at

Allowed MVP statuses:

- created
- brief_generated

### AgentRun

An AgentRun records one execution of an agent against a ticket.

Fields:

- id
- ticket_id
- agent_type
- provider
- model
- status
- started_at
- completed_at
- error_message

Allowed MVP agent_type:

- planning

Allowed MVP statuses:

- pending
- running
- completed
- failed

### Artifact

An Artifact stores agent-generated output.

Fields:

- id
- ticket_id
- agent_run_id
- artifact_type
- content
- created_at

Allowed MVP artifact_type:

- implementation_brief

### LLMProvider

An LLMProvider generates text from a prompt.

The provider interface must support:

- generate_text(prompt: str) -> str

Keep the interface simple.

## Backend API Contract

Implement these endpoints only.

### GET /health

Response:

{
"status": "ok",
"service": "incidentpilot-api"
}

### POST /tickets

Request:

{
"title": "string",
"description": "string"
}

Response:

{
"id": "uuid",
"title": "string",
"description": "string",
"status": "created",
"created_at": "timestamp",
"updated_at": "timestamp"
}

### GET /tickets/{ticket_id}

Returns one ticket.

Missing ticket returns 404.

### POST /tickets/{ticket_id}/planning-runs

Creates a planning AgentRun, generates an implementation brief, stores the artifact, updates the ticket status to brief_generated, and returns the run plus artifact.

Response:

{
"agent_run": {
"id": "uuid",
"ticket_id": "uuid",
"agent_type": "planning",
"provider": "mock|deepseek",
"model": "string",
"status": "completed",
"started_at": "timestamp",
"completed_at": "timestamp",
"error_message": null
},
"artifact": {
"id": "uuid",
"ticket_id": "uuid",
"agent_run_id": "uuid",
"artifact_type": "implementation_brief",
"content": "markdown",
"created_at": "timestamp"
}
}

### GET /tickets/{ticket_id}/artifacts

Returns artifacts for a ticket.

## Planning Agent

The planning agent must generate an implementation-ready markdown brief.

The output format must be exactly:

# Implementation Brief

## 1. Requirement Summary

## 2. Business Goal

## 3. Assumptions

## 4. Ambiguities / Questions

## 5. Affected Areas

## 6. Technical Approach

## 7. Task Breakdown

## 8. Test Strategy

## 9. Edge Cases

## 10. Risks

## 11. Definition of Done

## 12. Human Approval Points

Use this prompt template:

You are a senior software delivery and QAOps planning agent.

Create an implementation-ready brief for the following ticket.

This system is human-supervised. Do not assume agents can deploy, merge, or change production without approval.

Rules:

- Do not invent unknown system details.
- Mark uncertainty clearly.
- Prefer small, safe, reviewable tasks.
- Include tests.
- Include rollback or safety considerations where relevant.
- Include human approval points.
- Output markdown only.

Ticket title:
{title}

Ticket description:
{description}

## LLM Provider Rules

The application must be provider-agnostic.

Implement a simple provider interface in:

services/api/app/llm/base.py

First implementation:

services/api/app/llm/deepseek.py

DeepSeek provider must:

- read API key from environment variable
- read model name from config
- never hardcode secrets
- raise clean application errors on provider failure
- be mocked in tests

Implemented providers: mock (default), DeepSeek, Kimi (Moonshot). Provider can be selected per request via the `provider` field on `POST /tickets/{ticket_id}/planning-runs`. The `GET /llm/providers` endpoint reports which providers are configured (key present) without exposing secrets.

Do not implement Gemini, Claude, LangGraph, MCP, or autonomous tool calling unless explicitly instructed.

## Configuration Rules

Use environment variables.

Expected variables:

- ENVIRONMENT
- LLM_PROVIDER
- LLM_MODEL
- DEEPSEEK_API_KEY
- GCP_PROJECT_ID
- FIRESTORE_DATABASE

For local tests, defaults may use mock provider.

Never commit real secrets.

Do not create real .env files.

A .env.example file is allowed.

## Persistence Rules

Start with in-memory repositories when instructed.

Move to Firestore only when explicitly instructed.

Repository code must be isolated from API route handlers.

Do not call Firestore directly from route handlers.

Automated tests must not require GCP credentials.

## Testing Rules

Use pytest.

Minimum tests by MVP end:

1. GET /health returns 200
2. POST /tickets creates ticket
3. GET /tickets/{ticket_id} returns ticket
4. Missing ticket returns 404
5. POST /tickets/{ticket_id}/planning-runs creates completed planning run
6. Planning run creates implementation_brief artifact
7. GET /tickets/{ticket_id}/artifacts returns artifacts
8. LLM provider is mocked in tests
9. Provider failure produces clean failed AgentRun or clear error response

Testing requirements:

- no real LLM calls in tests
- no real GCP calls in tests
- no network required
- deterministic tests
- simple test data
- no excessive mocking complexity

## Error Handling Rules

Use clear HTTP errors.

- Missing ticket: 404
- Validation errors: FastAPI/Pydantic defaults
- LLM provider failure: return controlled error; do not expose secrets
- Internal errors: log useful details, but do not leak credentials

## Docker Rules

The backend Dockerfile must:

- use Python 3.12 slim
- install dependencies cleanly
- run Uvicorn
- listen on 0.0.0.0
- use port 8080
- not include secrets

Do not add Docker Compose unless explicitly instructed.

## GitHub Actions Rules

CI workflow:

.github/workflows/api-ci.yml

On pull request affecting services/api:

1. checkout
2. setup Python 3.12
3. install dependencies
4. run tests
5. build Docker image

Deploy workflow:

.github/workflows/api-deploy.yml

On merge to main:

1. authenticate to GCP using Workload Identity Federation
2. build Docker image
3. push image to Artifact Registry
4. deploy to Cloud Run

Do not use service account JSON keys.

## Terraform Rules

Terraform lives in:

infra/terraform/

Minimum infrastructure only:

- Artifact Registry
- Firestore database
- Cloud Run service
- Cloud Run service account
- IAM permissions for Firestore
- Secret Manager secret reference for DeepSeek API key

Do not add Pub/Sub, Eventarc, GKE, Cloud SQL, Redis, VPC, or complex modules.

Terraform changes must always include explanation of:

1. resources added
2. IAM impact
3. cost impact
4. security impact
5. commands to run

## Frontend Rules

Keep frontend minimal.

Required pages:

- create ticket
- ticket detail
- planning brief display

UI flow:

1. user enters ticket title and description
2. user creates ticket
3. user clicks generate planning brief
4. markdown brief is displayed

Do not add auth, dashboard complexity, design systems, charts, or admin panels.

## Documentation Rules

README must eventually include:

- what ForgeLoop does
- MVP scope
- architecture summary
- tech stack
- local setup
- tests
- deployment
- example ticket
- example generated brief
- future work clearly separated from MVP

docs/architecture.md must stay short and practical.

## Coding Style Rules

- Keep code simple.
- Prefer explicit names.
- Do not add comments unless logic is genuinely non-obvious.
- Avoid unnecessary abstractions.
- Avoid clever patterns.
- Avoid premature generalization.
- Keep functions small.
- Keep route handlers readable.
- Keep provider abstraction minimal.

## Git Rules

Before changing files:

- run git status

Do not commit unless explicitly asked.

Do not overwrite human changes.

Do not reformat unrelated files.

## Task Execution Protocol

For every task:

1. Read CLAUDE.md.
2. Run git status.
3. Inspect relevant files.
4. Produce a short plan first.
5. Wait for approval if in plan mode.
6. Implement only approved scope.
7. Add/update tests.
8. Run relevant tests.
9. Fix only relevant failures.
10. Summarize the diff.

Summary format:

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

## Planning Mode Rules

When asked to plan:

- do not edit files
- do not create files
- do not delete files
- do not apply patches
- inspect only
- return a concrete plan

Plan format:

1. Current repo observations
2. Files to create/change
3. Implementation steps
4. Tests to add/update
5. Commands to run
6. Out of scope
7. Risks/assumptions

## Approved Milestone Order

The active engineering scope is fixed at **32 tasks across 6 releases**. Do not add work beyond these. Marketing/product-growth (Release 7) is parked separately.

### Release 1 — Planning Platform (Tasks 1–12) — Complete

1. Backend health endpoint
2. Ticket API with in-memory repository
3. Planning AgentRun + Artifact with mock LLM provider
4. Provider abstraction cleanup
5. DeepSeek provider integration
6. Firestore repository
7. Dockerfile
8. Backend CI
9. Terraform minimum GCP infrastructure
10. Cloud Run deploy workflow
11. Minimal frontend
12. README and architecture docs

### Release 2 — Provider + Basic Usability (Tasks 13–15) — Complete

13. Kimi provider integration
14. Per-request provider selection (`GET /llm/providers` + UI selector)
15. Documentation alignment with product direction

### Release 3 — GitHub + Approval Foundation (Tasks 16–20)

- GitHub App or webhook integration (trigger agents from GitHub events)
- Branch creation
- PR creation
- Human approval gate workflow (explicit sign-off at each stage transition)
- Audit log (full history of agent runs, evaluations, and human decisions)

### Release 4 — Tool-based Coding Automation (Tasks 21–25)

- Tool runner abstraction (interface for invoking external coding tools)
- First tool runner integration (OpenHands or Aider)
- Dev task decomposition (break approved briefs into actionable dev tasks)
- Multi-candidate orchestration (run multiple agents/prompts, evaluate and select)
- Change request loop (human requests revision; agent reruns against feedback)

### Release 5 — Review + CI Intelligence (Tasks 26–29)

- AI-assisted PR review
- CI failure analysis
- Test run evaluation
- Prompt version tracking (which prompt produced which artifact)

### Release 6 — IncidentOps (Tasks 30–32)

- Incident triage agent
- Production failure analysis
- Remediation brief workflow

### Release 7 — Marketing / Product-Growth (Future, parked)

Not part of the active 32-task roadmap. Plan separately after Release 6 is done. Possible scope: product brief generator, landing page copy, marketing campaign planner, social post generator, cold outreach drafts, user feedback collector, competitor/research tracker.

Work-safe features (approval gates, audit log, output scoring, change request loop, prompt version tracking, repo safety profile, work-safe mode, DoD checklist, branch protection awareness) are folded into Releases 3–6 and do not add tasks beyond 32.

Do not skip ahead. Do not implement Release 3+ items unless explicitly instructed.

## Definition of MVP Done

The MVP is done when:

1. API runs locally
2. tests pass locally
3. ticket can be created
4. planning run can be executed
5. implementation brief artifact is generated
6. DeepSeek provider works via environment config
7. tests mock all LLM calls
8. data persists in Firestore
9. backend runs in Docker
10. backend deploys to Cloud Run
11. CI runs on pull requests
12. README explains setup and demo
13. scope remains limited to planning workflow

This is the hard stop.

After this, future phases can be planned separately.
