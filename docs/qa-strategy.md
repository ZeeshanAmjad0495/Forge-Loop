# ForgeLoop QA / STLC Strategy

QA is a first-class pipeline stage in ForgeLoop, not an afterthought. It is planned for Release 4.

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

Each layer produces a `QARunArtifact` stored in ForgeLoop. A layer must pass its quality gate before the workflow advances to the next stage.

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

All tools are invoked via ForgeLoop's tool runner abstraction (Release 5). Results are stored as artifacts — ForgeLoop does not re-implement any test execution logic.

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

## Current State

QA pipeline is not yet implemented. It is planned for Release 4 (Golden Path + Deterministic QA).

See `docs/roadmap.md` for release schedule and `docs/tooling-strategy.md` for the tool runner model and preferred tool choices.
