# ForgeLoop Security Architecture

Status: authoritative. Companion to `security-audit-findings.md` (the
finding register) — this document defines the *target* security model, the
controls that enforce it, and the residual risks the operator must own.

ForgeLoop is a human-supervised autonomous SDLC/STLC control plane that
delegates code execution to external agents (OpenHands, Aider) and tools
(Kody, Semgrep, …). Its security posture is therefore about **containment
and supervision**, not sandboxing the agents themselves.

---

## 1. Trust model (read this first)

ForgeLoop is, by design, a **single-operator control plane**:

- One administrative principal (`AUTH_ADMIN_EMAIL` / JWT). There is **no
  multi-tenant authorization layer**: a valid token is full control over
  every project, workspace, and execution surface. This is an explicit,
  documented property — *the JWT is a root credential* and must be
  protected as one (short TTL, never logged, rotated on exposure).
- Cross-*project* isolation is by **convention + service-layer
  cross-link checks**, not by an enforced per-tenant ACL. The concrete
  exploitable gap (an approval from project A satisfying a gate in
  project B) **is** fixed (M2, project-scoped approval lookup); the
  remaining "one token sees all projects" is accepted single-operator
  scope, not a defect to patch without a tenancy redesign (out of scope;
  would change product semantics and usability).
- The OpenHands/Aider runtimes are **delegated executors**. ForgeLoop
  confines *its own* process rigorously; it cannot constrain what a
  delegated agent does on the network. Deployment isolation (no prod
  credentials/network reachable from the agent runtime) is an operator
  responsibility, stated in §6.

Threat actors in scope: (a) the authenticated operator acting in error or
via a compromised token; (b) the LLM agent writing hostile content into a
workspace; (c) a network attacker who can reach the service; (d) a
compromised/hostile external service (Kody/OpenHands/LLM endpoint)
returning malicious responses. Out of scope: a malicious operator with
shell on the host (they already own everything), supply-chain compromise
of pinned dependencies (mitigated, not eliminated).

---

## 2. Defense-in-depth layers

| Layer | Control |
|---|---|
| Network ingress | App-level JWT auth on every endpoint except `/health`; body-size cap (H6); docs/openapi disabled in production (M9); CORS explicit allowlist (no wildcard/credentials). Operator must front Cloud Run with private ingress/IAP (§6). |
| AuthN | HS256 JWT, algorithm-pinned (no `alg=none`/confusion); constant-time credential compare; secret entropy enforced ≥32 (L1); `AUTH_ENABLED=false` refused outside an explicit local opt-in (H1). |
| AuthZ | Single-admin (see §1). Project-scoped approval lookup (M2) prevents cross-project gate bypass. Risky state transitions (commit, push, PR, merge, deploy, remediation) require an approved `Approval`. |
| Input | Pydantic validation; request body-size middleware (H6); Mongo equality helpers reject operator objects — NoSQL-injection guard (H7); no `pickle`/`eval`/`yaml.load`. |
| Execution boundary | All subprocesses `shell=False`, fixed server-built argv (request input never reaches argv), PATH-minimal env, `cwd` pinned, timeout + output cap. Git argv allow-list (`_run_git`). Command-runner allowlist is QA-tooling-only; interpreter escapes removed; shell-mode gated behind `COMMAND_RUNNER_ALLOW_SHELL` (H3). |
| Workspace confinement | `assert_workspace_safe` re-validated at *every* git/command/execute entry (H4) — system-root subtrees and HOME credential dirs are refused even with `WORKSPACE_ALLOW_OUTSIDE_ROOT` on (L3). B1 hard-sync fenced to `forgeloop/*` non-protected branches; per-workspace execution mutex prevents concurrent corruption. |
| State integrity | B1 sync eliminates cross-run *and* cross-dev-task bleed (incl. migration-stamped disposable DBs). Snapshot diff detects blocked-path writes post-agent. |
| Egress / SSRF | `validate_external_base_url` rejects metadata/link-local/reserved hosts and plaintext-to-public for every credentialed client; bounded response reads (Ollama H8, OpenHands bridge H9, GitHub, Kody); bridge-supplied ids sanitized before URL interpolation (H9). |
| Secrets | `SecretProvider` (name-only errors); token redaction on every git/Kody/GitHub error/audit/artifact path; executors run without `GITHUB_TOKEN` in env; `.gitignore` blocks `.env*`, `*.bak`, `*-service-account*.json`. |
| Observability | Audit events: server-set id/timestamp, actor = JWT subject (never request-settable). Langfuse optional, no-op without creds, secret-key via provider. |
| Error handling | Global handler returns opaque 500; internal detail logged server-side only (M8). |
| Supply chain | (residual) dependency ranges + CI action pinning — see §5/L4–L5. |

---

## 3. Production-safety guarantees (the "never do disastrous things" contract)

Enforced by code, defaulting safe (all gates default off):

1. **No deploy.** No deployment code path exists in the control plane.
2. **No merge without approval.** Merge to a protected branch is never
   constructed; integration runs target a fresh `forgeloop/*` branch only.
3. **No push without approval + config + scope.** Push requires draft
   `approved_for_creation` + `GITHUB_INTEGRATION_ENABLED` +
   `GITHUB_PUSH_ENABLED` + token + a `forgeloop/`-prefixed non-protected
   branch. All flags default false.
4. **No destructive git on real repos.** `reset --hard`/`clean -fd` is
   fenced to `forgeloop/*` non-protected branches *and* a workspace path
   re-validated as non-system/non-credential at operation time (H4).
5. **No production data access.** ForgeLoop holds no prod DB credentials;
   the only DB it touches is its own repository store. Agent runtimes
   must not be given prod reachability (operator duty, §6).
6. **Commit always approval-gated**, project-scoped (M2).
7. **Auditability.** Every agent/tool/human state transition emits an
   audit event with a non-forgeable actor.

---

## 4. Audit-finding → control mapping

CRITICAL C1 → operator key rotation + `.gitignore` hardening (shipped).
C2 → §1 trust model documented; concrete sub-bug fixed via M2.
HIGH: H1 auth-disable guard ✅ · H3 allowlist/shell gate ✅ · H4 op-time
confinement ✅ · H5 (cross-project IDOR) → §1 + M2 ✅(scoped) · H6 body
cap ✅ · H7 Mongo injection guard ✅ · H8 Ollama SSRF/bounded ✅ · H9
bridge SSRF/bounded/id-sanitize ✅.
MEDIUM: M2 ✅ · M4 LLM timeout/redaction ✅ · M5 URL validator ✅ · M8
opaque 500 ✅ · M9 docs gating ✅ · M1/M3/M6/M7/M10 → tracked, lower
severity, see register.
LOW: L1 ✅ · L2 ✅ · L3 ✅ · L4/L5/L6 → operator/infra hardening (§5).

All fixes shipped with tests; the audit-action meta-test and the strong
controls in §2 are regression-guarded by the suite (1251 passing).

---

## 5. Known residual risks (operator-owned / tracked)

- **C2 single-admin scope** — accepted; mitigate by treating the token as
  root, short TTL, network-restricting the service (§6).
- **M3** — `integration_runs` uses a second scoped git boundary
  (fixed-argv, no allow-list backstop). Low risk today; tracked.
- **M6/M7** — redaction is known-literal; hostile-JSON depth not bounded.
- **L4** — dependency ranges are floor-only; add upper bounds + committed
  lockfile + `pip-audit`/`osv-scanner` in CI.
- **L5** — pin GitHub Actions to SHAs; restrict Cloud Run ingress;
  encrypted remote Terraform state.
- **L6** — audit trail is append-only by practice, not tamper-evident
  (no hash chain). Acceptable for single-operator; revisit for
  compliance.
- Agent egress is unbounded by ForgeLoop (delegated-executor model).

---

## 6. Operator security requirements (must do)

1. **Rotate any exposed credential** (the C1 set) and never commit/paste
   secrets; keep `.env` out of git (enforced) and delete `.env.bak`.
2. Run with `AUTH_ENABLED=true`, a ≥32-char random `AUTH_TOKEN_SECRET`,
   short `AUTH_TOKEN_TTL_SECONDS`.
3. Front the service with private ingress / identity-aware proxy; do not
   expose it (or `/docs`) to the public internet.
4. Give the OpenHands/Aider runtime **no production credentials or
   network reachability** — the agent is delegated and unconstrained
   on egress by ForgeLoop.
5. Keep all execution/push/integration flags **off** until deliberately
   needed; `COMMAND_RUNNER_ALLOW_SHELL` only with full understanding it
   grants arbitrary execution.
6. Restrict `WORKSPACE_ALLOW_OUTSIDE_ROOT` to trusted dev repos only;
   never register a workspace at a system or credential path (now also
   refused in code).

This architecture is intentionally calibrated to ForgeLoop's actual
deployment (single operator, delegated executors) — it adds enforced
containment and supervision without changing the product's usability or
functionality, per the project constraint.
