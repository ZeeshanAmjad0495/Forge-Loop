# ForgeLoop QA / STLC Strategy

QA is a first-class pipeline stage in ForgeLoop, not an afterthought. The foundational `CheckDefinition` / `CheckRun` data model and repository layer are **implemented in Release 4**. Real external scanner execution is not implemented — that belongs to the future Execution Bridge.

---

## Deterministic QA First

Deterministic checks run before any LLM review step. An LLM agent must not approve a stage without evidence from actual tool/test runs stored as artifacts. QA evidence is stored and auditable — it is not self-asserted by an agent.

Order of operations within any QA gate:
1. Native tests (unit / integration / coverage)
2. Deterministic security and static analysis tools
3. Browser / E2E tests
4. LLM-assisted review (only after deterministic checks pass)
5. Human approval (always required at the final gate)

---

## Test Pyramid

```
           [Accessibility]     ← axe-core
          [Security Scanning]  ← Semgrep, OSV-Scanner, Trivy, Gitleaks
         [End-to-End / Browser] ← Playwright Test Agents (primary)
        [Integration / API]    ← pytest, Jest/Vitest
       [Unit]                  ← pytest (existing)
```

Each layer produces a `CheckRun` (stored via `CheckDefinition` repository) or links to an `Artifact`. A layer must pass its quality gate before the workflow advances to the next stage. Real tool execution is not yet wired — `CheckRun` records are created manually or programmatically via the API.

---

## Target Tools by Layer

| Layer | Primary Tool(s) | Notes |
|-------|----------------|-------|
| Unit / integration | pytest (existing), Jest/Vitest | Already in use |
| E2E / browser | Playwright Test Agents | Primary browser QA lane |
| AI-driven test generation | TestZeus | Secondary / experimental — not primary |
| Security (SAST) | Semgrep | |
| Security (dependencies/containers) | OSV-Scanner, Trivy | |
| Secret scanning | Gitleaks | |
| Accessibility | axe-core | |
| Observability / prompt/cost tracing | Langfuse | Added in Release 4 |

TestZeus is not the primary QA tool. Playwright Test Agents form the main browser QA lane. TestZeus may be evaluated later as a supplement after the Playwright lane is stable.

When real execution is wired (future Execution Bridge), tools will be invoked via ForgeLoop's `ToolRunner` abstraction (implemented in Release 5). Results will be stored as `Artifact`s — ForgeLoop does not re-implement any test execution logic.

---

## Quality Gates

Each gate is a checkpoint before the workflow can advance:

| Gate | Condition to pass |
|------|------------------|
| Unit / integration | All existing tests pass; new tests pass |
| E2E | Critical user flows verified |
| Security | No high/critical CVEs in dependencies; no SAST blockers |
| Accessibility | No WCAG 2.1 AA violations |
| Human QA approval | Human reviews QA summary and signs off |

Human approval is required at the final QA gate before a ticket can be marked QA-passed and advance to deployment.

---

## Artifacts

Each tool invocation creates a `QARunArtifact`:

```
QARunArtifact {
  id
  ticket_id
  agent_run_id
  tool_name          # "semgrep", "playwright", "pytest", etc.
  tool_version
  status             # passed | failed | warning
  findings           # structured list of issues
  raw_output         # full tool output
  created_at
}
```

---

## Work-Safe Rules

- No QA tool run advances the workflow automatically — results must be reviewed
- Security findings above a configurable severity threshold block advancement
- QA tool invocations are logged in the audit trail
- No proprietary code is sent to external scanning services unless explicitly approved

---

## Out of Scope (current releases)

- AI test generation (beyond what TestZeus provides)
- Self-healing tests
- Flake detection and retry logic
- Visual regression testing
- Load / performance testing
- Mutation testing

---

## Repository abstraction rule

QA check definitions and check run records must be persisted via the repository abstraction (`RepositoryProvider`). QA pipeline logic must not call Firestore or GCP APIs directly — this ensures the QA pipeline works in local profile without cloud credentials.

---

## CI failure evidence (Task 30)

Externally observed CI failures can be recorded into ForgeLoop as `CIEvent`s alongside check runs, linked to PR drafts / dev tasks / subtasks / check runs. A `CIAnalysis` can be requested per event; it invokes the configured LLM provider with a structured prompt and stores a parsed diagnostic (summary, likely root causes, suggested debugging steps, suggested follow-up action, conclusion). Analyses are advisory only — they do not claim a fix was applied, do not recommend merge or deploy, and never include secrets. Live webhook / CI provider API integration is out of scope; ingestion is manual or programmatic via the ForgeLoop API.

---

## Production incident evidence (Task 31)

Production incidents and operational issues can be recorded into ForgeLoop as `Incident`s, optionally linked to a code repository, `CIEvent`, PR draft, dev task, or subtask. An `IncidentAnalysis` can be requested per incident; it invokes the configured LLM provider with a structured triage/remediation prompt and stores a parsed diagnostic (summary, impact, likely root causes, immediate safe actions, remediation plan, prevention actions, recommended follow-up action, failure category). Analyses are advisory only — they do not claim production was changed, do not recommend direct deployment or rollback, and never include secrets or customer data. An optional `prepare-remediation` endpoint returns a non-persisted remediation work item draft; any DevTask creation remains a human action and requires the existing approval gate before any coding runner picks it up. Live monitoring integration (Cloud Logging, Sentry, Datadog, etc.) is out of scope; ingestion is manual or programmatic via the ForgeLoop API.

---

## Current State

**Release 4 is implemented.** `CheckDefinition` and `CheckRun` entities exist with full CRUD and repository abstraction. Deterministic QA metadata and result tracking are in place.

Real external scanner execution (running Semgrep, Trivy, Playwright, etc. as subprocesses or via API) is **not implemented** and belongs to the future Execution Bridge.

CI failure ingestion (`CIEvent`, `CIAnalysis`) and incident ingestion (`Incident`, `IncidentAnalysis`) are implemented in Release 6.

See `docs/roadmap.md` for the full release breakdown and `docs/tooling-strategy.md` for tool runner choices.

---

## Deferred: Frontend unit tests (S6)

Frontend helper modules (`apps/web/src/lib/status.ts`, `formatting.ts`, `apps/web/src/api/client.ts`) contain pure functions that are candidates for Vitest unit tests. Adding Vitest was deferred in S6 to avoid devDependency churn and CI script changes. Revisit when frontend test coverage is explicitly requested.
