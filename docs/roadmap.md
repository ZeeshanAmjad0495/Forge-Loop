# ForgeLoop Roadmap

Releases 1–6 (32 tasks) are complete. The bounded controlled-adoption roadmap **Tasks 75–85** is also complete. The currently authorized active scope is **Release 10 — Operational Execution Layer, Tasks 86–100** (see the Release 10 section near the end of this file). The scope is fixed: **do not start any task beyond 100, or re-expand earlier "deferred" items, without an explicit update to this file.** This file + `docs/architecture.md` + the repo `CLAUDE.md` are the authoritative direction.

> **Authoritative release scheme:** Releases 1–6 (Tasks 1–32) → controlled adoption (Tasks 75–85) → Release 10 — Operational Execution Layer (Tasks 86–100). The `docs/release-8…release-12-*-summary.md` files are **historical exploratory artifacts** from an earlier informal numbering experiment; they are *not* authoritative and are unrelated to this Release 10. In particular `docs/release-10-evaluation-lab-summary.md` (old Tasks 57–62, "Evaluation Lab") is a different, superseded "Release 10". Historical summaries are preserved and never deleted (CLAUDE.md rule 10).

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

---

## Execution Bridge — Foundations (post-32, additive)

Tasks beyond the fixed 32 are scoped one at a time and must not be expanded without approval.

- Task 33 — Local Workspace Manager: `Workspace` model, safe path validation, register/create/inspect/archive API, and a minimal UI. Metadata + empty-directory creation only. No shell, no git, no GitHub, no PR, no OpenHands, no source-file mutation, no remote clone.
- Task 34 — Safe command runner (future). Will introduce controlled command execution against a workspace. Not in Task 33.

See [`docs/execution-bridge.md`](execution-bridge.md).

---

## Post-32 Controlled-Adoption Roadmap (Tasks 75–85) — Bounded

This is the **complete** post-32 controlled-adoption scope, and it is **complete**. It is succeeded by **Release 10 — Operational Execution Layer (Tasks 86–100)**, defined below and authorized by Task 86. The bound is now: **no task beyond 100 may be started without an explicit update to this file.** Historical release summaries above are retained and unchanged. The direction is *controlled adoption, not endless expansion* — items previously phrased "always out of scope" are **deferred / controlled adoption**, never silent scope creep.

| Task | Title | Status |
|------|-------|--------|
| 75 | Model routing + Kimi cost guard | Complete |
| 76 | Cost visibility + budget CostRecords | Complete |
| 77 | RunnerRouter (lightweight default, OpenHands approval-gated) | Complete |
| 78 | ContextPack hardening + token reduction | Complete |
| 79 | Valkey/Redis local cache, rate-limit, ephemeral state | Complete |
| 80 | Durable workflow + event foundation (Phase A: in-memory EventBus/WorkflowEngine) | Complete |
| 81 | Controlled project-memory vector retrieval | Complete |
| 82 | Free observability (metrics/structured logs) | Complete |
| 83 | Advisory-only auto-remediation | Complete |
| 84 | CLI-first UX + lightweight dashboard clarity | Complete |
| 85 | Documentation / CLAUDE.md / roadmap alignment | Complete |

### Post-pack stabilization fixes (from the 75–85 audit)

Bounded, non-feature fixes surfaced by the post-pack stabilization audit. Not new scope.

- **R-D — Complete.** CLI global flags (`--dry-run`/`--token`/`--base-url`) now parse **before or after** the subcommand (argparse parent parser with suppressed defaults + env fallback in `main()`). Audit had found the documented post-subcommand order errored. +3 regression tests.
- **R-E — Complete.** Documented that the API **fail-closes** without `AUTH_TOKEN_SECRET` when `AUTH_ENABLED=true` (correct secure default, not a bug) in `.env.example` and `docs/cli.md`, with the local no-auth opt-in path.
- **R-A — Resolved (ProbePilot, separate repo).** PR #12 was already merged; PR #13 (`forgeloop/probepilot-s6-integration`) branch pushed and PR #13 merged to ProbePilot `main`. No `gh` CLI available in-env; GitHub PR merge done via the web UI by the owner.

### Decisions matrix (adopted / deferred / rejected)

| Item | Decision | Why |
|---|---|---|
| Kimi | Adopt — **approval-gated expensive fallback only** | Burns balance too fast for default use |
| DeepSeek | Adopt — default hosted reasoning provider | Cheaper than Kimi, sufficient for most planning/review |
| Ollama | Adopt — local cheap workflows | Summaries, classification, compression, memory extraction |
| OpenHands | Keep — route selectively, **approval-gated** | Too slow for every task; good for broad multi-file work |
| Lightweight runner (Aider/OpenCode-style) | Adopt — default for narrow coding | Faster/cheaper |
| Valkey/Redis | Adopted (Task 79) — cache/locks/rate-limit, **never source of truth** | First infra step |
| NATS | Adopted as Phase-B adapter (designed, not forced) | Local-first fanout; better fit than Kafka |
| Temporal | Adopted as Phase-B adapter (designed, not forced) | Durable human-supervised workflows |
| Kafka | **Deferred/avoid** | Too heavy for ForgeLoop's volume |
| Pub/Sub / Eventarc | **Deferred** — later cloud adapter behind `EventBus` | Only relevant on GCP |
| K3s | **Optional spike only**, documented | Use only if worker isolation becomes necessary |
| Vector DB / RAG | Adopted controlled (Task 81) — project-memory summaries only, off by default | No broad raw-code RAG |
| Chroma/Qdrant/pgvector | **Deferred** future local adapters | In-memory deterministic store is the smallest workable option |
| Prometheus/OpenTelemetry/Grafana | Adopt free/local foundation (Task 82); OTel = config flag, not imported | Free and useful |
| Sentry / Cloud Logging | **Deferred** | Optional / cloud-only |
| Auto-remediation | Adopt **advisory only** (Task 83) | No deploy/merge/branch/PR without human approval |
| Slack/email notifications | **Deferred** until workflows stable | Not core |
| Complex dashboard / billing / multi-tenancy / MCP | **Deferred / out of scope now** | CLI-first; not needed for current use |

---

## Release 10 — Operational Execution Layer (Tasks 86–100) — Authorized, Active

Tasks 75–85 built cost/router/context/runner/observability *foundations*
but several were only advisory or not force-wired into real execution.
**Release 10 makes those foundations operational** and adds the optional
Phase-B infra adapters and a controlled draft-PR path. It is bounded to
Tasks 86–100. **No task beyond 100 without a further explicit update to
this file.**

Release 10 adds **no new product surface** beyond the table below. It
preserves every existing safety boundary: human approval for risky
transitions, no merge/deploy/force-push/protected-branch bypass, no
secret exposure, DB remains the source of truth, Kimi stays an
approval-gated expensive fallback, OpenHands is never the default
runner, and auto-remediation stays advisory / draft-PR only.

| Task | Title | Type | Status |
|------|-------|------|--------|
| 86 | Release 10 roadmap / architecture / CLAUDE.md alignment | Docs/governance | Complete |
| 87 | Enforce ModelRouter everywhere (no hidden provider selection) | Backend cost-safety | Complete |
| 88 | Wire CostRecord + BudgetGuard into real execution | Backend cost-control | Complete |
| 89 | Enforce ContextPack across agent workflows | Token/context | Complete |
| 90 | Wire RunnerRouter into real execution (OpenHands not default) | Runner orchestration | Complete |
| 91 | Runner locks + workspace isolation (force-wired) | Safety/reliability | Complete |
| 92 | Local background worker execution (DB-backed jobs) | Backend worker | Complete |
| 93 | Temporal Phase B — migrate exactly one workflow (optional, gated) | Optional durable workflow | Complete |
| 94 | NATS Phase B — optional local event fan-out (off by default) | Optional event adapter | Complete |
| 95 | Valkey Phase B — cache / rate-limits / ephemeral state | Cache/rate-limit | Complete |
| 96 | Observability Phase B — real metrics wiring (free/local) | Observability | Complete |
| 97 | CLI-first command layer (no deploy/merge commands) | CLI/usability | Complete |
| 98 | Dashboard execution timeline (simple, operational) | Frontend usability | Complete |
| 99 | Controlled branch/PR automation policy update | Docs/policy | Complete |
| 100 | Draft PR creation end-to-end (controlled; never merge/deploy) | End-to-end backend/runner | Complete |

### Release 10 boundaries (binding)

- Every real LLM call flows through ModelRouter/routed execution and is
  cost-recorded + budget-checked. Direct provider choice is allowed only
  inside provider adapter/factory internals.
- ContextPacks are required for model-facing workflows; large raw
  context is warned/blocked.
- RunnerRouter is mandatory for coding/remediation execution; OpenHands
  is selected only for broad/complex, human-approved work.
- Runner execution acquires locks + workspace isolation; concurrent
  same-task/workspace runs are blocked.
- Temporal/NATS/Valkey Phase-B adapters are **optional, config-gated,
  disabled by default**, with local DB fallback; the DB/audit log
  remains the source of truth. Kafka and Pub/Sub–Eventarc stay deferred.
  K3s remains an optional spike only.
- Branch/PR automation is policy-first (Task 99), then controlled
  draft-PR only (Task 100): never auto-merge, auto-deploy, force-push,
  or bypass protected branches; approvals/checks gate the path.
- Observability/metrics never expose secrets, tokens, prompts, or PII.

### Controlled Branch/PR Automation Policy (Task 99) — binding

Task 99 is documentation/governance only — it **authorizes** the
bounded automation Task 100 implements, and nothing beyond it. No app
code, runner, or GitHub-API change is made by Task 99.

**Allowed (only when every condition holds):** create a *fresh*
`forgeloop/*` branch off a non-protected base; commit human-approved
runner output to it locally; push that `forgeloop/*` branch; open a
**draft** pull request for human review. Every one of these is
**config-gated** (dedicated flags, all default **false**), requires an
**approved `Approval`** for the target, and runs **only after the
deterministic QA/check gate passes**. The DB/audit log stays the source
of truth; every action is audited.

**Forbidden (always, regardless of config):** merging any PR;
marking a PR ready-for-review automatically; deploying or releasing;
force-pushing; pushing to / branching off / targeting a protected
branch; creating or mutating GitHub branch-protection rulesets;
destructive git (`reset --hard` outside the fenced sync, history
rewrite, `clean -fd` outside the workspace, branch deletion on remote);
auto-review/auto-approve of the PR; touching any repo or branch outside
the connected project's `forgeloop/*` scope.

Task 100 must implement exactly this envelope behind the
flags-default-false gates and the existing approval + repo-safety
controls; it may not widen it. Any expansion needs a further explicit
update to this file.
