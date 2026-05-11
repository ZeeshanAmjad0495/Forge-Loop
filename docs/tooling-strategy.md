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

**Releases 1–6 are complete (all 32 tasks).** The following tooling foundations are implemented:

The ToolRunner abstraction (Task 26) is implemented. The OpenHandsRunner integration foundation (instruction-package dry-run) is implemented (Task 27): ForgeLoop can prepare a deterministic OpenHands instruction package from a dev task, store it on a `ToolRun`, and record a manually-pasted result.

OpenHands controlled local execution (Task 36) is implemented as an opt-in handoff: `POST /dev-tasks/{id}/openhands/execute` with `mode=local` runs the configured OpenHands CLI once inside a registered workspace, `shell=False`, with a stripped env, a timeout cap, and an output-byte cap. The handoff is **disabled by default** (`OPENHANDS_EXECUTION_ENABLED=false`) and additionally requires `OPENHANDS_COMMAND` to be set and an approved approval on the dev task (or its task decomposition). Change evidence is gathered via metadata-only filesystem snapshots — ForgeLoop never invokes `git` here. Blocked-path violations from the repo safety profile mark the `ToolRun` as `failed/requires_human_action`. **Task 36 does not create branches, does not call GitHub, does not open PRs, does not merge, and does not deploy** — git branch workflow is Task 37, PR creation is Task 38, and human review remains required between Task 36 and those follow-ons. See [`docs/execution-bridge.md`](execution-bridge.md) for the full contract.

The PR draft workflow foundation (Task 28) is implemented as metadata tracking only: ForgeLoop generates a deterministic PR title/body from a dev task or subtask (plus optional `ToolRun`, check runs, requirement, epic, and repo safety profile), tracks human approval via a status machine, and lets a user paste the eventual external PR URL/number back into the record. **No GitHub API call is made** — ForgeLoop does not create branches or open PRs in this build. GitHub draft-PR creation is a future task.

The Kodus/Kody PR review integration foundation (Task 29) is implemented as tracking only: ForgeLoop builds a deterministic Kody review-request package from a `PullRequestDraft` (project, repo, linked dev task / subtask / requirement / epic / `ToolRun`, QA evidence from check runs, repo safety profile, human approval status, review focus areas) and stores it on a `PullRequestReview` record with status `pending`. A manually-supplied result can also be recorded directly, or a pending review can later be completed with a conclusion (`approved`, `changes_requested`, `comment_only`, `failed`, `skipped`, `requires_human_review`) and structured findings. **No external Kody/Kodus API call is made** — `KODY_REVIEW_ENABLED` defaults to `false` and the adapter's `execute()` raises `NotImplementedError`. Completing a review does not approve or merge the parent PR draft.

The CI failure ingestion and analysis foundation (Task 30) is implemented as manual/programmatic ingestion only: ForgeLoop accepts `CIEvent`s through its API, links them to PR drafts / dev tasks / subtasks / check runs / code repositories, and produces an advisory `CIAnalysis` by invoking the configured LLM provider with a structured prompt. Parsed fields include failure summary, likely root causes, suggested debugging steps, affected areas, recommended follow-up action, and a failure category (`flaky_test`, `code_regression`, `dependency_issue`, `configuration_issue`, `infrastructure_issue`, `unknown`, `needs_human_review`). **No GitHub Actions, GitLab CI, CircleCI, or other CI provider API is called.** ForgeLoop does not execute or rerun CI jobs, does not create branches or PRs, does not edit code, and does not auto-fix. Failed LLM invocations are persisted as `status="failed"` analyses with `error_message`.

The production / incident ticket workflow foundation (Task 31) is implemented as manual/programmatic ingestion only: ForgeLoop accepts `Incident`s through its API, links them to code repositories / `CIEvent`s / PR drafts / dev tasks / subtasks, and produces an advisory `IncidentAnalysis` by invoking the configured LLM provider with a structured triage/remediation prompt. Parsed fields include incident summary, impact assessment, likely root causes, immediate safe actions, remediation plan, prevention actions, affected areas, recommended follow-up action, and a failure category (`code_regression`, `configuration_issue`, `infrastructure_issue`, `dependency_issue`, `data_issue`, `security_issue`, `flaky_external_service`, `unknown`, `needs_human_review`). An optional `prepare-remediation` endpoint returns a non-persisted `RemediationWorkItemDraft` for human review; ForgeLoop does not auto-create a DevTask, branch, or PR. **No live monitoring integration is performed: ForgeLoop does not call Cloud Logging, Sentry, Datadog, OpenTelemetry, GitHub webhooks, Slack, email, or any monitoring provider.** ForgeLoop does not auto-detect incidents, does not auto-remediate, does not deploy, does not roll back, and does not run shell or coding tools. Failed LLM invocations are persisted as `status="failed"` analyses with `error_message`.

The project memory learning loop foundation (Task 32) is implemented as a human-supervised candidate flow: ForgeLoop can request an LLM-assisted distillation of a single completed source (`ci_analysis`, `incident_analysis`, `pr_review`, `check_run`, `tool_run`, `approval`, `dev_task`, `subtask`) into one or more `ProjectMemoryCandidate`s, classified by `memory_type` (`architecture_decision`, `project_rule`, `coding_standard`, `testing_rule`, `deployment_rule`, `approved_approach`, `rejected_approach`, `known_risk`, `known_failure_pattern`, `human_feedback`, `important_file`, `prompt_note`, `qa_learning`, `incident_learning`, `cost_note`, `custom`). Manual candidates can also be created directly. **No durable project memory is written without explicit human approval.** Approval appends a deterministic, marker-tagged block to the existing `ProjectContext` free-form fields; rejection records a reason; PATCH is allowed only while the candidate is `proposed`. **ForgeLoop does not use vector databases, RAG, embeddings, evaluator/swarm orchestration, background learning, schedulers, or external research agents.** Failed LLM invocations are persisted as `status="failed"` learning runs with `error_message`. The candidate parser drops items whose `memory_type` falls outside the closed Literal — keeping the system resilient to real-LLM variance without leaking unknown enum values into storage. Cost / context optimization, ResearchScout, Evaluation Lab, local durable runtime, and post-32 stabilization work are out of scope.

**Future Execution Bridge work (not in current roadmap):** Real OpenHands subprocess/API execution, actual GitHub branch and PR creation, live Kody/Kodus external API calls, live CI provider API integration, live monitoring provider integration, and automated deployment or rollback. These are planned for a future Execution Bridge milestone and must not be implemented in the current codebase without explicit approval.

See `docs/roadmap.md` for release schedule.
