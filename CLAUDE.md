# CLAUDE.md

# IncidentPilot MVP — Claude Code Operating Instructions

You are the primary coding agent for this repository.

This project must be completed as a focused MVP within 1–2 weeks. Do not expand scope. Do not add speculative features. Do not build future phases unless explicitly instructed.

## Product Definition

IncidentPilot is a human-supervised autonomous SDLC platform.

The long-term vision is:

- agents analyze requirements
- agents create implementation plans
- agents decompose tasks
- agents create branches
- agents generate tests
- agents open PRs
- agents review PRs
- agents analyze CI failures
- agents generate incident reports
- humans approve risky actions, merges, deployments, and production changes

The MVP is much smaller.

## MVP Goal

The MVP accepts a ticket/user story, creates an agent run, generates an implementation-ready brief using an LLM provider, stores the generated artifact, and exposes everything through an API and minimal UI.

The MVP proves the core workflow:

Ticket
→ AgentRun
→ PlanningAgent
→ ImplementationBrief Artifact
→ Human reads/reviews the brief

## Hard MVP Scope

Build only these capabilities:

1. FastAPI backend
2. Ticket creation and retrieval
3. AgentRun creation for planning
4. ImplementationBrief artifact generation
5. LLM provider abstraction
6. DeepSeek provider as the first real provider
7. Kimi provider only if explicitly instructed later
8. Firestore persistence
9. Minimal frontend
10. Dockerized backend
11. GitHub Actions CI
12. Cloud Run deployment
13. Terraform for minimum GCP infrastructure
14. README and architecture documentation

## Explicitly Out of Scope

Do not implement these in the MVP:

- autonomous code editing
- branch creation
- PR creation
- PR review agent
- incident triage agent
- production auto-fixes
- Pub/Sub
- Eventarc
- Kubernetes
- Slack integration
- GitHub issue integration
- GitHub App
- authentication
- user accounts
- RBAC
- billing
- multi-tenancy
- complex dashboard
- background workers
- vector database
- RAG
- MCP server
- swarm orchestration
- LangGraph
- long-running agent workflows

If asked to implement any out-of-scope item, state that it is outside the MVP and propose the smallest future placeholder only if necessary.

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

Before DeepSeek is implemented, use a mock provider.

Do not implement Kimi, Gemini, Claude, LangGraph, MCP, or tool calling unless explicitly instructed.

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

- what IncidentPilot does
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

Follow this exact order:

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

Do not skip ahead.

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
