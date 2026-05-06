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

## Release 3 — Requirements + Task Planning Engine (Tasks 17–21)

Scope (high-level — detailed tasks defined per sprint):

- Requirements intake (structured input, not just free-text tickets)
- Task decomposition (break approved planning briefs into dev tasks and subtasks)
- Task lifecycle management (status tracking, sequencing, dependencies)
- Human approval gate at planning-to-task transition
- Audit log foundation (agent run history, human decisions)

---

## Release 4 — QA / STLC Pipeline (Tasks 22–25)

Scope:

- QA agent run type (test generation, test execution via tool runners)
- Integration with QA tools (TestZeus, Playwright Test Agents)
- Security scanning integration (Semgrep, OSV-Scanner, Trivy)
- Quality gates: each stage must pass before advancing
- QA artifacts stored in ForgeLoop (`QARunArtifact`)

See `docs/qa-strategy.md` for full QA direction.

---

## Release 5 — Tool Runner + Code Automation (Tasks 26–29)

Scope:

- Tool runner abstraction (interface for invoking external coding tools)
- First tool runner integration (OpenHands or Aider)
- Code review integration (PR-Agent or Kodus/Kody)
- Multi-candidate orchestration (run multiple agents, evaluate, select best)

See `docs/tooling-strategy.md` for tool catalogue and delegation principle.

---

## Release 6 — Production + Learning Loop (Tasks 30–32)

Scope:

- Production monitoring and incident triage
- Remediation brief workflow (failure → ticket → planning → fix)
- Learning loop (project memory updated from outcomes, QA results, production events)

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

Do not implement Release 3+ items unless the current task explicitly requests them.
