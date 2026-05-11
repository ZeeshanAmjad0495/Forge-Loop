# ForgeLoop Roadmap

32 tasks across 6 releases. The active engineering scope is fixed — do not add tasks beyond 32 without explicit approval.

---

## Release 1 — Core Planning Platform (Tasks 1–12) — Complete

1. Backend health endpoint
2. Ticket API with in-memory repository
3. Planning AgentRun + Artifact with mock LLM
4. Provider abstraction cleanup
5. DeepSeek provider integration
6. Firestore repository
7. Dockerfile
8. Backend CI (GitHub Actions)
9. Terraform minimum GCP infrastructure
10. Cloud Run deploy workflow
11. Minimal React frontend
12. README and architecture docs

---

## Release 2 — Provider + Usability + Project Context (Tasks 13–16) — Complete

13. Kimi (Moonshot) provider integration
14. Per-request provider selection (`GET /llm/providers` + UI selector)
15. Auth/login (JWT, single admin user)
16. Project-aware dashboard + project context/memory

---

## Release 3 — Requirements + Task Planning Engine (Tasks 17–21) — Complete

Scope (implemented):

- Structured requirements intake (not just free-text tickets)
- Requirement analysis and clarification questions
- Task/subtask decomposition from approved planning briefs
- Task lifecycle management (status tracking, sequencing, dependencies)
- Human approval gates at planning-to-task transitions
- Audit event foundation (agent run history, human decisions)
- Project context and project memory

---

## Strategy note (post-Release 3)

The original broad plan for Releases 4–6 has been narrowed based on deep research findings:

- **Avoid tool sprawl.** Do not integrate many tool runners or QA agents at once.
- **Build one golden path first.** Validate the full loop with a single runner before adding more.
- **Deterministic QA before LLM review.** No LLM agent should approve a stage without evidence from actual tool/test runs stored as artifacts.
- **OpenHands** is the designated primary coding runner. Aider and Cline are local/manual fallbacks only.
- **Playwright Test Agents** are the primary browser QA lane. TestZeus is secondary/experimental.
- **Kodus/Kody** is the target PR review layer.
- **Langfuse** is added earlier (Release 4) for prompt tracing, cost tracking, and token records.
- **No typed project memory upgrade to RAG/vector DB yet.** Structured typed memory first.
- **Avoid Temporal, Kestra, LangGraph, MCP** unless a clear, specific need appears.
- **Local-first, cloud-optional.** Every Release 4–6 feature must work without GCP. Cloud services are provider implementations, not hard dependencies. New features that require persistence, secrets, artifacts, or observability must go through provider abstractions — not call GCP APIs directly from route handlers or business logic.

---

## Release 4 — Golden Path + Deterministic QA (Tasks 22–25) — Complete

Scope:

- Repo connection + repo safety profile (branch protection awareness, no-force-push rules)
- Deterministic QA/security bundle: Semgrep, OSV-Scanner, Trivy, Gitleaks, axe-core, native test/coverage tools
- Playwright / browser QA lane (Playwright Test Agents as primary E2E tool)
- Langfuse tracing: prompt versions, cost records, token usage per agent run

All deterministic checks run before any LLM review step. Results are stored as QA artifacts.

See `docs/qa-strategy.md` and `docs/tooling-strategy.md`.

---

## Release 5 — Tool Runner + PR Workflow (Tasks 26–29) — Complete

Scope:

- ToolRunner abstraction (single interface for invoking external coding tools)
- OpenHandsRunner as the primary coding runner (first and only runner until validated)
- PR draft workflow (task output → branch → PR draft)
- Kodus/Kody PR review integration — Task 29 lands the tracking + adapter foundation only. ForgeLoop records review request packages and externally-supplied review results as `PullRequestReview`s with structured findings and audit events; it does not call Kody/Kodus APIs.

ForgeLoop does not integrate multiple coding runners at once. OpenHands is the first and primary runner. Aider and Cline are local/manual fallbacks only. OpenCode, Hermes Agent, and OpenClaw remain secondary adapters for later. Multi-candidate orchestration is deferred until the single-runner workflow is stable.

See `docs/tooling-strategy.md`.

---

## Release 6 — CI + Incident + Learning Loop (Tasks 30–32) — Complete

Scope (implemented):

- CI failure ingestion and analysis (connect CI events → ForgeLoop tickets) — Task 30 lands the foundation only. ForgeLoop accepts manually or programmatically recorded CI failure events as `CIEvent`s, links them to PR drafts / dev tasks / subtasks / check runs, and produces advisory LLM-assisted `CIAnalysis` records with structured root causes and suggested debugging steps. ForgeLoop does not call GitHub Actions, GitLab CI, CircleCI, or any CI provider; it does not run shell, edit code, create branches, open PRs, or auto-fix.
- Production/incident ticket workflow (failure → triage → remediation brief) — Task 31 lands the foundation: manual/programmatic `Incident` ingestion, advisory `IncidentAnalysis`, optional non-persisted `RemediationWorkItemDraft`. No live monitoring integration, no auto-remediation, no deploy.
- Project memory learning loop (outcomes, QA results, production events update project memory) — Task 32 lands the foundation: LLM-distilled or human-authored `ProjectMemoryCandidate`s from CI / incident / PR review / check run / tool run / approval / dev task / subtask sources, with explicit human approve/reject. Approved candidates append deterministic blocks to `ProjectContext`. No vector DB, no RAG, no embeddings, no background learning, no automatic memory writes.

The fixed 32-task core ForgeLoop roadmap (Releases 1–6) is now complete.

---

## Release 7 — Marketing / Product-Growth (Parked)

Not part of the active 32-task roadmap. Subsumed by LaunchPilot (a ForgeLoop Studio module). Plan separately after Release 6 is complete.

See `docs/forge-loop-studio.md`.

---

## Work-Safe Capabilities

The following cross-cutting capabilities are folded into Releases 3–6 and do not add tasks beyond 32:

- Human approval gates at risky transitions
- Audit log (agent runs, evaluations, human decisions)
- Output scoring / evaluation
- Change request loop (human feedback → agent reruns)
- Prompt version tracking
- Repo safety profiles (branch protection, no-force-push)
- Work-safe / dry-run mode for workplace use
- DoD checklist enforcement

---

## Rule

Do not implement Release 4+ items unless the current task explicitly requests them.
