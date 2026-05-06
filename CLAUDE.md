# CLAUDE.md

# ForgeLoop — Claude Code Instructions

You are the primary coding agent for this repository.

ForgeLoop is a human-supervised autonomous SDLC + STLC control plane. It helps manage projects, requirements, tickets, agent runs, artifacts, approvals, QA loops, code review loops, and tool-runner workflows.

ForgeLoop is the control plane. It should not rebuild coding agents from scratch. When possible, future code execution should be delegated to existing tools such as OpenHands, Aider, Cline, OpenCode, Hermes Agent, TestZeus, Playwright Test Agents, Kodus/Kody, PR-Agent, Semgrep, OSV-Scanner, Trivy, axe-core, and similar tools.

## Current Build State

Releases 1 and 2 are implemented.

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

The current active work is moving into Release 3.

## Active Roadmap

The active engineering roadmap is fixed at 32 tasks across 6 releases.

- Release 1: Core planning platform — complete
- Release 2: Provider + usability + project context — complete
- Release 3: Requirements + task planning engine
- Release 4: QA/STLC pipeline
- Release 5: Tool runner + code automation
- Release 6: Production + learning loop

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

- GitHub issue/PR automation
- approval gates
- audit log
- QA agents
- tool runners
- OpenHands/Hermes/Cline/Aider/OpenCode integration
- evaluator/swarm orchestration
- production incident workflows
- MCP server
- LangGraph
- vector DB/RAG
- billing/multi-tenancy
- ForgeLoop Studio modules
- marketing workflows

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
