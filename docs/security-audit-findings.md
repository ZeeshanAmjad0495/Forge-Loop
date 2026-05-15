# ForgeLoop Security Audit — Findings Register

Status: read-only audit complete (#43). Fixes are tracked in the dedicated
remediation phase (#45). This register is the authoritative list; each item
carries severity, location, exploit, and remediation.

Method: 6 parallel boundary audits (auth/authz, subprocess/git, network/SSRF,
secrets, data-isolation/prod-safety, web-input/supply-chain), OWASP-ASVS
aligned. Threat model: an authenticated operator (single-admin token) and,
transitively, the LLM agent writing into a workspace, attempting to break
confinement, isolation, or the production-safety guarantees; plus an
attacker with network reach to the service.

---

## CRITICAL

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| C1 | **Live credentials in the working tree.** Real GitHub PAT (push scope), DeepSeek, Kimi, Kodus, Langfuse keys present in `services/api/.env`, `services/api/.env.bak`, `apps/web/.env`. NOT in git history/tracked files (verified) — risk is the on-disk `.env.bak` duplicate + chat exposure. | `services/api/.env*`, `apps/web/.env` | **Operator action:** rotate all 5 credential sets; delete `.env.bak`. Code-side: `.gitignore` hardened (`*.bak`, `*.env.backup`) — done. |
| C2 | **No per-project / per-resource authorization (cross-project IDOR).** `require_auth` only proves a valid token exists; every by-ID route (`/workspaces/{id}`, `/approvals/{id}`, branches, tool-runs, audit, execution) loads by raw ID with no ownership/project scoping. Single-admin token == root over every project, secret-bearing config, and code-execution surface. | `app/auth.py:41-53`; all `app/routes/*.py` | Introduce an authorization boundary keyed on subject + owning project; 403 on mismatch. Until a tenant model exists, scope all by-ID reads/mutations by `project_id` and document single-tenant-admin trust. |

---

## HIGH

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| H1 | **Auth-disable bypass.** `AUTH_ENABLED=false` makes the entire control plane (incl. execution endpoints) anonymous via one env var, no startup refusal/banner. | `app/auth.py:42-43`, `config.py` | Refuse to start unless explicit `ENVIRONMENT=local` + dedicated opt-in; loud startup banner when auth disabled. |
| H2 | **Login unthrottled & unaudited.** No rate limit / lockout / backoff / failed-attempt audit on `POST /auth/login`; single static admin credential → online brute force. | `app/routes/auth.py:9-19` | Per-IP + global rate limit + lockout; audit success/failure (no password); enforce admin password min length. |
| H3 | **Command-runner allowlist is effectively no containment.** Opt-in `shell=True` check definitions run `bash -lc <raw>` with metachar validation deliberately skipped; `bash`/`node`/`npx`/`python` on the default allowlist make even non-shell mode an interpreter escape (`bash -c …`). Blocklist only matches argv[0]. Reachable once `COMMAND_RUNNER_ENABLED` + an authenticated definition write. | `app/services/check_execution.py:154-163`, `models/commands.py:226-254`, `config.py:144` | Remove interpreters from default allowlist; gate `shell=True` behind a dedicated default-false flag + approval; correct docstrings. |
| H4 | **Workspace confinement is registration-time only & opt-out.** `WORKSPACE_ALLOW_OUTSIDE_ROOT` flip → any host path; even on, no operation-time re-confinement — persisted `root_path` is trusted by every destructive git op (`reset --hard`, `clean -fd`, integration merges). Mis-registered workspace → B1 sync wipes the developer's real repo working tree. | `app/services/workspace_paths.py:33-52`, `git_workflow.py` (`_require_workspace_ready_git`) | Re-assert `is_relative_to(root)` at every git/command entry point; treat the opt-out as per-workspace + loud startup audit. |
| H5 | **Cross-project IDOR on direct-ID resources.** `get/update/archive/inspect workspace`, `decide approval`, branches do no project scoping at the route boundary; isolation is service-layer convention only. | `routes/workspaces.py:100-176`, `routes/approvals.py:50-88`, `repositories*.get()` | Project-scoped predicate on all by-ID reads/mutations. |
| H6 | **Pervasive missing input constraints + no body-size cap.** ~50 model files have no `Field` length limits; FastAPI default body size unbounded → JSON-bomb / memory DoS / unbounded LLM spend; `external_url` unvalidated scheme. | `app/models/*.py`, `app/main.py` | `max_length` on all free-text; ASGI body-size middleware (413); constrained URL types w/ scheme allowlist. |
| H7 | **Mongo operator injection.** `list_by_field*` / `find_approved_for_target` pass body-derived values straight into `find({field: value})`; a dict value (`{"$ne": null}`) bypasses scoping → cross-tenant read / approval-gate bypass. | `app/repositories_mongo.py:172-188,292,360-363,727-744` | Coerce filter values to scalar / reject `dict` values centrally in `MongoDocumentRepository`. |
| H8 | **Ollama client: plaintext HTTP, unvalidated base URL, unbounded read.** SSRF (e.g. `169.254.169.254`), cleartext prompt leakage, memory-DoS via unbounded `resp.read()`. | `app/llm/ollama.py:29,33-44,75`, `config.py:35` | Scheme/host validation (https unless loopback/RFC1918 + explicit insecure opt-in); bounded read; explicit timeout. |
| H9 | **OpenHands HTTP bridge: unbounded reads + response-derived URL interpolation + unvalidated base URL.** Hostile/compromised bridge can reshape follow-up request URLs (ids from its own response) or memory-DoS; off-box base URL exfiltrates instruction content in cleartext, no client auth. | `app/services/openhands_execution.py:504-561,255,366,415-416`, `config.py:75` | Cap all reads; validate/encode `conversation_id`/`start_task_id` (UUID shape) before interpolation; enforce loopback/TLS. |

---

## MEDIUM

| ID | Finding | Location | Remediation |
|----|---------|----------|-------------|
| M1 | JWT has no `iss`/`aud`, 24h TTL, no revocation/jti. | `app/auth.py:28-30` | Add+verify iss/aud; shorten TTL/refresh; jti denylist; document secret rotation. |
| M2 | Implicit approval lookup not project-bound — `find_approved_for_target` scans all projects on the no-`approval_id` path. | `repositories*.find_approved_for_target`, `openhands_execution.py:662`, `git_workflow.py:424-435` | Add `project_id` filter to both repo impls. |
| M3 | `integration_runs._git` bypasses the `_run_git` allow-list (defense-in-depth drift); `_restore_head` switches to an unvalidated `original_branch`. | `app/services/integration_runs.py:60-75` | Shared low-level `_spawn_git` primitive / replicate `_check_top_level`; validate `original_branch`. |
| M4 | DeepSeek/Kimi providers: no `timeout=`; error interpolates raw SDK exception (parity gap vs `openai_compatible`'s `type(exc).__name__`). | `app/llm/deepseek.py:13-23`, `kimi.py:13-23` | Explicit timeout; `type(exc).__name__` redaction. |
| M5 | No central https/loopback validator for credentialed base URLs (Kody/OpenHands/Ollama/OpenAI-compat over `http://` leak tokens). | `config.py:35,39,75,92`, clients | Shared `validate_external_base_url` helper applied across all clients. |
| M6 | Redaction is known-literal/prefix heuristic — misses encoded or non-prefixed token echoes. | `kody_client.py:54-68`, `github_client.py:69-87` | Add generic high-entropy/token-pattern scrub before truncation on every error path. |
| M7 | Hostile external JSON parsed without depth/type hardening (kody/openhands vs github's defensive wrap). | `kody_client.py:156-161`, `openhands_execution.py:521,555,579-608` | Assert top-level type, bound nesting, never reflect parsed values into request URLs. |
| M8 | Information disclosure: `detail=str(exc)` returned verbatim (filesystem/DB/provider internals); no catch-all handler. | ~30 routes incl. `routes/common.py:30-32`, `commands.py:66,114,137` | Map exceptions to fixed messages; global 500 handler; never echo `str(exc)` for FS/DB/provider. |
| M9 | Cloud Run `allUsers` invoker documented; `/docs` & `/openapi.json` enabled (anon schema disclosure if public). | `README.md:408-414`, `app/main.py` | Private Cloud Run + IAP; disable docs when `ENVIRONMENT=production`. |
| M10 | `blocked_paths` / secret-path heuristics case-sensitive (macOS `.ENV`/`Secrets/` evasion); agent containment is detective (post-hoc snapshot), not preventive. | `git_workflow.py:208-267`, `workspace_snapshot.py:73-77` | Case-fold matching on case-insensitive hosts; document detective containment. |

---

## LOW

| ID | Finding | Location |
|----|---------|----------|
| L1 | `AUTH_TOKEN_SECRET` length/entropy not enforced (only non-empty). | `config.py:185-190` |
| L2 | `.gitignore` lacked explicit `*.bak`/`*.env.backup`. **Fixed in this commit.** | `.gitignore` |
| L3 | `_dangerous_targets` exact-match denylist incomplete (`/root`,`/opt`,`~/.ssh`, subdirs pass). | `workspace_paths.py:18,26-30` |
| L4 | Floor-only dependency ranges, no committed lockfile; no `pip-audit`/`osv-scanner` in CI. | `services/api/pyproject.toml` |
| L5 | Terraform ingress unrestricted; GH Actions tag-pinned (not SHA); CI job missing `permissions:`. | `infra/terraform/main.tf`, `.github/workflows/*` |
| L6 | Audit trail append-only by practice but not tamper-evident (`save`=`upsert`, no hash chain). | `audit_writer.py`, `repositories_mongo.py:307-312` |
| L7 | HttpOpenHands instruction-file discovery by extension+exists heuristic (defense-in-depth). | `openhands_execution.py:238-244` |

---

## Verified strong controls (do not regress)

- Git subprocess boundary: `shell=False`, PATH-only env, argv allow-list (`_check_top_level`); `pull/fetch/merge/rebase/reset/clean/remote/config` never constructed in `_run_git`; push helper bans force/mirror/tags/upstream/delete and redacts tokens.
- Layered no-push / no-deploy / no-merge: status + `GITHUB_INTEGRATION_ENABLED` + token + `GITHUB_PUSH_ENABLED` + forgeloop-prefixed non-protected branch; all default off. Commit always approval-gated. No deploy path exists.
- B1 `sync_workspace_to_branch_head`: `reset --hard`/`clean -fd` fenced to forgeloop-prefixed, non-protected branches only.
- Per-workspace execution mutual exclusion (concurrency hardening #42) prevents same-workspace corruption.
- Secret provider returns name-only errors; token redaction applied on every observed git/kody/github error/audit/artifact path; executors run with minimal env (GITHUB_TOKEN not in executor env).
- JWT algorithm pinned (HS256, no `alg=none`/confusion); constant-time credential compare; startup fails closed if `AUTH_ENABLED=true` + empty secret; only `/health` anonymous.
- CORS explicit allowlist (no wildcard, no credentials+wildcard); no `pickle`/`eval`/`yaml.load`/`exec`; Pydantic+JSON only.
- `github_repo.parse_owner_repo` is a strong single SSRF chokepoint (strict regex, github.com only, no `http://`/enterprise/`..`); project `repo_url` never reaches an outbound host.
- `model_routing` is pure decision logic — no I/O / SSRF surface.
- Audit `actor_email` is the JWT subject, never request-settable (no actor spoofing).

---

## Remediation plan (executed in #45, post-ProbePilot, per approved order)

Priority order: C2 → H1/H3/H4/H5 → H6/H7 → H8/H9 → M-series → L-series.
C1 is operator-action (key rotation) + the `.gitignore` hardening shipped here.
Each fix must preserve usability/functionality (owner constraint) and ship
with tests; the audit-action and meta-test guards already prevent
regression of the strong controls above.
