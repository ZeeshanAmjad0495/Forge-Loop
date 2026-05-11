# ForgeLoop Tooling Strategy

## Core Principle

ForgeLoop is a **control plane**, not a coding agent. It does not reimplement tools that already exist. When code execution, testing, scanning, or review is needed, ForgeLoop invokes existing open-source tools, stores their output as artifacts, and enforces human approval before any result advances to the next stage.

Tool runners must not assume a cloud runtime. Invocation, result storage, and observability must go through ForgeLoop's provider abstractions so the local profile works without GCP.

---

## Delegation Model

```
ForgeLoop owns:
  project context, workflow state, task lifecycle,
  artifact store, approval gates, audit trail

ForgeLoop delegates to tools:
  code generation → OpenHands (primary) / Aider / Cline (fallback)
  test execution  → Playwright Test Agents (primary) / TestZeus (secondary)
  code review     → Kodus/Kody
  security scan   → Semgrep / OSV-Scanner / Trivy / Gitleaks
  accessibility   → axe-core
  observability   → Langfuse (prompt tracing, cost, token records)
```

Integration pattern for each tool:
1. ForgeLoop invokes tool via API or CLI
2. Tool output is stored as a `ToolRun` artifact in ForgeLoop
3. Human reviews output (or ForgeLoop evaluates it automatically for low-risk stages)
4. Human approves or requests changes before the workflow advances

---

## Anti-Sprawl Rules

Do not integrate many tool runners or QA agents at once. The strategy is:

- Start with **one coding runner** (OpenHands) and validate the full loop before adding more.
- Start with **one browser QA lane** (Playwright) before adding AI-based test generators.
- Add tools only when a clear, specific gap exists — not speculatively.
- Avoid workflow engines (Temporal, Kestra, LangGraph, MCP) until a concrete need appears.

---

## Preferred Primary Tools

| Category | Primary | Fallback / Secondary |
|----------|---------|---------------------|
| Coding runner | OpenHands | Aider (local/manual), Cline (local/manual) |
| Browser / E2E QA | Playwright Test Agents | TestZeus (experimental, not yet primary) |
| PR review | Kodus / Kody | — |
| SAST | Semgrep | — |
| Dependency / container scan | OSV-Scanner, Trivy | — |
| Secret scanning | Gitleaks | — |
| Accessibility | axe-core | — |
| Observability / cost / prompt tracing | Langfuse | — |

---

## Tool Catalogue

### Code Automation

| Tool | Role | Priority |
|------|------|---------|
| OpenHands | Autonomous coding agent (API invocation, returns diff/PR) | **Primary** |
| Aider | AI pair programmer (CLI) | Local/manual fallback |
| Cline | VS Code AI coder (CLI or API) | Local/manual fallback |
| OpenCode | Terminal coding agent | Secondary adapter (later) |
| Hermes Agent | Lightweight agent framework | Secondary adapter (later) |
| OpenClaw | Coding agent | Secondary adapter (later) |

OpenHands is the designated first runner. The single-runner workflow must be validated before adding additional runners. Multi-candidate orchestration is deferred to after Release 5.

### QA / Test Execution

| Tool | Role | Priority |
|------|------|---------|
| Playwright Test Agents | E2E browser test automation | **Primary** |
| pytest / Jest / Vitest | Unit and integration tests (native, already in use) | **Primary** |
| TestZeus | AI-driven test generation and execution | Secondary / experimental |

### Code Review

| Tool | Role |
|------|------|
| Kodus / Kody | AI code review platform — target PR review layer |

### Security Scanning

| Tool | Role |
|------|------|
| Semgrep | Static analysis (SAST) |
| OSV-Scanner | Open source vulnerability scanning |
| Trivy | Container and dependency scanning |
| Gitleaks | Secret scanning |

### Accessibility

| Tool | Role |
|------|------|
| axe-core | Accessibility rule engine |

### Observability

| Tool | Role |
|------|------|
| Langfuse | Prompt version tracking, cost records, token usage per agent run |

---

## What ForgeLoop Never Does

- Does not write production code directly without a tool runner
- Does not autonomously merge, deploy, or remediate without human approval
- Does not send proprietary or customer data to external tools unless explicitly approved
- Does not rebuild functionality that existing tools already provide well

---

## Current State

The ToolRunner abstraction (Task 26) is implemented. The OpenHandsRunner integration foundation (instruction-package dry-run) is implemented (Task 27): ForgeLoop can prepare a deterministic OpenHands instruction package from a dev task, store it on a `ToolRun`, and record a manually-pasted result. Actual OpenHands execution remains disabled by default (`OPENHANDS_EXECUTION_ENABLED=false`).

The PR draft workflow foundation (Task 28) is implemented as metadata tracking only: ForgeLoop generates a deterministic PR title/body from a dev task or subtask (plus optional `ToolRun`, check runs, requirement, epic, and repo safety profile), tracks human approval via a status machine, and lets a user paste the eventual external PR URL/number back into the record. **No GitHub API call is made** — ForgeLoop does not create branches or open PRs in this build. GitHub draft-PR creation is a future task.

The Kodus/Kody PR review integration foundation (Task 29) is implemented as tracking only: ForgeLoop builds a deterministic Kody review-request package from a `PullRequestDraft` (project, repo, linked dev task / subtask / requirement / epic / `ToolRun`, QA evidence from check runs, repo safety profile, human approval status, review focus areas) and stores it on a `PullRequestReview` record with status `pending`. A manually-supplied result can also be recorded directly, or a pending review can later be completed with a conclusion (`approved`, `changes_requested`, `comment_only`, `failed`, `skipped`, `requires_human_review`) and structured findings. **No external Kody/Kodus API call is made** — `KODY_REVIEW_ENABLED` defaults to `false` and the adapter's `execute()` raises `NotImplementedError`. Completing a review does not approve or merge the parent PR draft.

See `docs/roadmap.md` for release schedule.
