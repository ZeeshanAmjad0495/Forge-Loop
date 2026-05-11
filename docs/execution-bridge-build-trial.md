# ForgeLoop Execution Bridge Build Trial

## Verdict

**PASS WITH MANUAL CODING FALLBACK** — ForgeLoop drove a small project end-to-end through the human-supervised loop. Every stage that does not require live OpenHands or a live GitHub remote produced real, persisted records and real on-disk effects. OpenHands live execution and GitHub draft PR publication were **not live-tested** because their integrations were intentionally left disabled per the task brief.

## Environment

| Field | Value |
|---|---|
| ForgeLoop branch | `main` |
| ForgeLoop commit | `acce0576ee18e1c74f9526160331f75007bf0236` (Task 39) |
| ForgeLoop source-tree changes | **none** — only untracked `.forgeloop/` (trial workspace) and `services/api/.forgeloop/` (stub) |
| Trial project path | `/Users/zeeshan.amjad/Documents/ai/incidentpilot/.forgeloop/workspaces/probe-pilot-mini` |
| Python (system) | 3.13.7 |
| Python (ForgeLoop venv) | 3.12.12 |
| Node | v20.19.4 (frontend `apps/web` directory does not exist on disk; frontend smoke not applicable) |
| `REPOSITORY_PROVIDER` | `memory` |
| `LLM_PROVIDER` | `mock` |
| `AUTH_ENABLED` | `true` (logged in as `admin@example.com`) |
| `COMMAND_RUNNER_ENABLED` | `true` |
| `GIT_WORKFLOW_ENABLED` | `true` |
| `GIT_COMMIT_ENABLED` | `true` |
| `OPENHANDS_EXECUTION_ENABLED` | `false` (dry-run prepare exercised; live execution not configured) |
| `GITHUB_INTEGRATION_ENABLED` | `false` |
| `GITHUB_PUSH_ENABLED` | `false` |
| `FORGELOOP_WORKSPACE_ROOT` | `/Users/zeeshan.amjad/Documents/ai/incidentpilot/.forgeloop/workspaces` (overridden so the trial root is separate from `services/api/.forgeloop/workspaces/`) |

## Trial Project

- **Name:** probe-pilot-mini
- **Goal:** Minimal local API endpoint monitor used as a target for the trial.
- **Stack:** FastAPI + pytest + httpx; local JSON file storage under `data/`.
- **MVP endpoints implemented:** `GET /health`, `POST /endpoints`, `GET /endpoints`, `POST /endpoints/{id}/check`, `GET /endpoints/{id}/checks`.
- **Final status:** 7 pytest tests pass; ForgeLoop-driven local commits visible at `060ad79` and `75c4103` on branch `forgeloop/probe-pilot-mini-endpoint-checks` on top of initial skeleton `d19f841`. No remote configured, no push.

## Workflow Results

| Stage | Status | Evidence | Notes |
|---|---|---|---|
| Auth | pass | JWT issued from `/auth/login` | Local admin credentials |
| Project setup | pass | project id `cdd66b7f-cfa3-4bcb-9824-c40d6af82a60` | |
| Project context | pass | `PUT /projects/{id}/context` | architecture/test/safety notes set |
| Repository record | pass | repo id `0652bda9-c246-485a-b13a-cbdd6e80dc2c`, provider=`other`, `repo_url=file://…/probe-pilot-mini` | |
| Safety profile | pass | profile id `56c4cc14-…`; protected `main`; required `pytest`; secrets paths blocked | |
| Workspace registration | pass | ws id `c4d50ca8-…`, type `local_existing`, status `ready`, real `.git/` present | |
| Workspace inspection | pass | `is_git_repo=true`, `file_count_estimate=9` initially | |
| Requirement creation | pass | req id `aac50ece-…` (`ready_for_analysis`) | |
| Requirement analysis | pass | analysis `72710d7c-…`, readiness `ready_for_planning` (mock provider) | |
| Task decomposition | pass | 2 dev tasks + subtasks generated (mock provider); agent_run `a3b90ccc-…` | See Issue #1 — mock produced an inverted dependency |
| Approval gates | pass | 6 approvals approved (requirement_analysis, task_decomposition, dev_task, revision_work_item, + 2 cleanup of earlier malformed approvals) | See Issue #2 — approval API accepted empty `target_id` |
| Branch creation | pass | branch `forgeloop/probe-pilot-mini-endpoint-checks`, base `main`, real `git switch -c` on disk | |
| Command definitions | pass | `backend_pytest` → `python -m pytest -q` | |
| Check definitions | pass | `backend_tests` (type `tests`, blocking) | |
| Baseline check execution | pass | check_run `cdac064d`, command_run `c04ad59f`, exit 0, 1 passed | |
| OpenHands prepare (dry_run) | pass | tool_run `2039cb1b-…` (`runner=openhands`, `mode=dry_run`, 10 instructions) | |
| OpenHands live execution | **not live-tested** | — | Intentionally disabled; would require `OPENHANDS_EXECUTION_ENABLED=true` + a configured `OPENHANDS_COMMAND` |
| Manual implementation result recorded | pass | `POST /tool-runs/{id}/openhands/record-result` updated tool_run to `requires_human_action` with summary + output | |
| Post-implementation check | pass | check_run `c32ac37a`, command_run `5c0e4b9f`, exit 0, 6 passed | |
| Git inspection | pass | `dirty=True`, 1 changed + 4 untracked detected pre-commit | |
| Local commit | pass | commit `060ad79`, 5 files committed via `POST /workspace-branches/{id}/commit` | Real commit on disk |
| PR draft | pass | pr_draft `a1a242be-…`, provider=`local`, status `approved_for_creation` after `POST /pr-drafts/{id}/approve` | |
| GitHub draft PR | **not live-tested** | `400: CodeRepository provider 'other' is not 'github'` | See Issue #3 — gate ordering vs docs |
| PR review (manual) | pass | review `215144dd-…`, conclusion `changes_requested`, 1 blocking finding | |
| Review feedback import | pass | 1 created / 0 skipped; feedback `c6b4182e-…` (blocking, tests, file_path `tests/test_checks.py`) | |
| Manual low-value feedback | pass | feedback `50daa471-…` created and **rejected** via PATCH (status=rejected) | |
| Plan revision | pass | revision_work_item `162950e1-…`, feedback auto-transitioned to `revision_planned` | |
| Revision approval gate | pass | revision_work_item approval `450ecd9c-…` approved before `proposed → approved` accepted | |
| Revision implementation | pass (manual fallback) | Added `test_check_failure_when_timeout_raised` to `tests/test_checks.py` (7 tests pass) | OpenHands not live-tested |
| Revision check execution | pass | check_run `c228d61b`, command_run `4c986600`, exit 0, 7 passed | |
| Revision commit | pass | commit `75c4103` on same branch | See Issue #4 — `.DS_Store` was committed because trial `.gitignore` did not exclude it |
| Revision lifecycle | pass | revision: in_progress → implemented → checks_passed → ready_for_review → resolved | |
| Feedback resolution | pass | feedback `c6b4182e-…` resolved via `POST /review-feedback/{id}/resolve` with summary | |
| Memory learning run | pass | run `3a6918bd-…` (source `pr_review`, provider `mock`), 2 candidates created | |
| Memory candidate approval | pass | candidate `888537d9-…` (`testing_rule`) approved | |
| Memory candidate rejection | pass | candidate `0250ef11-…` (`known_failure_pattern`) rejected with reason | |
| Audit trail | pass | 69 audit events on project, covering every stage (see counts below) | |

### Audit-event counts on the project

```
6  approval_approved              6  approval_requested
3  check_execution_completed      3  check_execution_requested
3  command_run_completed          3  command_run_requested
3  git_inspection_completed       2  workspace_commit_prepared
2  workspace_commit_created       2  dev_task_updated
2  memory_candidate_created       2  tool_runner_definition_created
1  check_definition_created       1  code_repository_created
1  command_definition_created     1  memory_candidate_approved
1  memory_candidate_rejected      1  memory_learning_completed
1  memory_learning_requested      1  openhands_package_prepared
1  openhands_result_recorded      1  pr_draft_approved
1  pr_draft_prepared              1  pr_review_completed
1  pr_review_requested            1  project_memory_learned
1  repo_safety_profile_updated    1  requirement_analyzed
1  requirement_created            1  review_feedback_created
1  review_feedback_imported       1  review_feedback_rejected
1  review_feedback_resolved       1  revision_work_item_planned
6  revision_work_item_updated     1  task_decomposition_created
1  workspace_branch_created       1  workspace_inspected
1  workspace_registered
```

## Commands Run

Preflight + setup (run from the ForgeLoop root):

```
git status
python -m pytest -q                         # ForgeLoop backend: 728 passed in 12.91s
mkdir -p .forgeloop/workspaces/probe-pilot-mini/{app,tests}
cd .forgeloop/workspaces/probe-pilot-mini
git init -b main
git -c user.name=ForgeLoopTrial -c user.email=trial@local add -A
git -c user.name=ForgeLoopTrial -c user.email=trial@local commit -m "Initial probe-pilot-mini skeleton"
```

ForgeLoop backend launch (PATH-only env for command runner inherits the venv):

```
set -a; . /tmp/forgeloop-trial.env; set +a
source .venv/bin/activate
cd services/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --log-level warning
```

Everything from Part 4 onward was driven via `curl` against the running backend. Trial-app pytest is invoked by ForgeLoop only — `python -m pytest -q` with cwd = workspace root, three times (baseline, post-implementation, post-revision). All three exited 0.

## Checks

- **Pre-implementation:** `check_run cdac064d` / `command_run c04ad59f` — 1 passed, exit 0.
- **Post-implementation:** `check_run c32ac37a` / `command_run 5c0e4b9f` — 6 passed, exit 0.
- **Final (post-revision):** `check_run c228d61b` / `command_run 4c986600` — 7 passed, exit 0.

## Files Changed in Trial Project

Across the two ForgeLoop-driven commits on `forgeloop/probe-pilot-mini-endpoint-checks`:

```
app/main.py             (extended: endpoint CRUD + manual check)
app/storage.py          (new: JSON file storage)
tests/conftest.py       (new: isolated_data_dir fixture)
tests/test_endpoints.py (new: 2 tests)
tests/test_checks.py    (new: 3 tests, then +1 timeout test in revision)
.DS_Store               (accidentally committed in revision — see Issue #4)
```

Initial skeleton commit (manual, pre-ForgeLoop) added:

```
pyproject.toml
README.md
.gitignore           (does NOT include .DS_Store — Issue #4)
app/__init__.py
app/main.py          (initial /health only)
tests/__init__.py
tests/test_health.py
```

## ForgeLoop Issues Found

### Issue #1 — Mock task decomposition produces inverted dependency

- **Severity:** low
- **Area:** `task_decomposition_agent.py` (mock provider)
- **Symptom:** The mock decomposition placed `Implement backend API endpoint` with `depends_on=[docs_task_id]` — i.e., it asserted the code task depends on the docs task, the wrong direction. Caused `PATCH /dev-tasks/{id}` to refuse `proposed → ready` with `dependencies not completed`.
- **Evidence:** `/tmp/devtasks.json` (initial state). Worked around by PATCHing `depends_on=[]`.
- **Suggested fix:** Either generate sensible dependency direction in the mock, or have the mock leave `depends_on` empty by default.
- **Blocks using ForgeLoop for personal projects?** No — only affects mock provider. A real LLM provider would not be evaluated here.

### Issue #2 — `POST /approvals` accepts empty `target_id`

- **Severity:** medium
- **Area:** `services/api/app/models/approvals.py` and the approvals route handler
- **Symptom:** `target_id=""` is silently accepted; an Approval row is created with empty `target_id` and can even be transitioned to `approved`. Such a row never matches any real target and is dead data.
- **Evidence:** The two initial approvals I created from a shell pipeline where the `target_id` shell-variable was unset still appear in `GET /projects/{id}/approvals` with `target_id=''` and status `approved`.
- **Suggested fix:** Add `Field(min_length=1)` (or a validator) on `ApprovalCreate.target_id`, and reject empty values with `422`.
- **Blocks using ForgeLoop for personal projects?** No, but it pollutes the audit/approval store and means an authoring bug in a client cannot be caught by the API.

### Issue #3 — GitHub publication gate ordering disagrees with docs

- **Severity:** low (docs/code drift, not a safety issue)
- **Area:** `services/api/app/services/github_publication.py` (or equivalent)
- **Symptom:** `docs/execution-bridge.md` Task 38 lists `GITHUB_INTEGRATION_ENABLED=true` as the first gate (HTTP `409 GITHUB_INTEGRATION_DISABLED`). In practice, `POST /pr-drafts/{id}/create-github-draft` returned `400 "CodeRepository provider 'other' is not 'github'"` first — the repo-provider validator fires before the kill-switch check.
- **Evidence:** `/tmp/gh_block.json` body.
- **Suggested fix:** Either reorder gates so `GITHUB_INTEGRATION_ENABLED` is checked first (so a globally-disabled integration always returns the same `409` regardless of repo config), or update the docs to reflect the actual order.
- **Blocks using ForgeLoop for personal projects?** No. The endpoint still blocks correctly.

### Issue #4 — Trial workspace `.gitignore` did not exclude `.DS_Store`; ForgeLoop committed it

- **Severity:** low (workspace hygiene, not a ForgeLoop bug)
- **Area:** trial-side hygiene, but worth surfacing because ForgeLoop will faithfully commit whatever the diff shows.
- **Symptom:** macOS Finder dropped a `.DS_Store` into the trial repo between commits. Because the workspace `.gitignore` did not list it and the safety profile did not list it, the revision commit included it.
- **Evidence:** revision commit `75c4103` `changed_files` includes `.DS_Store`.
- **Suggested fix:** Add `.DS_Store` to ForgeLoop's built-in commit-path secrets/noise blocklist (Task 37 already has a secrets blocklist that could be extended with a small OS-noise list), or document a recommended baseline `.gitignore` for ForgeLoop workspaces.
- **Blocks using ForgeLoop for personal projects?** No — but easy to embarrass yourself on macOS without it.

### Issue #5 — Post-branch-creation inspection reports `base_branch` = current branch

- **Severity:** very low (cosmetic)
- **Area:** git workflow inspector that runs immediately after `git switch -c`.
- **Symptom:** Immediately after creating `forgeloop/probe-pilot-mini-endpoint-checks` off `main`, `inspection.base_branch` in the response equals `forgeloop/probe-pilot-mini-endpoint-checks`. The `WorkspaceBranch.base_branch` record correctly stores `main`.
- **Evidence:** `/tmp/branch.json` `inspection.base_branch` vs `workspace_branch.base_branch`.
- **Suggested fix:** When the workspace branch row knows its `base_branch`, prefer that over re-derived inspector state in the post-creation response.
- **Blocks using ForgeLoop for personal projects?** No.

## Manual Steps Required

- **OpenHands live execution:** not exercised. Manual coding by Claude Code was used as the implementation step, recorded against the prepared OpenHands ToolRun via `POST /tool-runs/{id}/openhands/record-result`. To live-test, configure `OPENHANDS_EXECUTION_ENABLED=true`, `OPENHANDS_COMMAND`, and `OPENHANDS_ALLOWED_ARGS`.
- **GitHub PR creation:** not exercised. Would also require `code_repository.provider="github"` and a real GitHub-hosted URL. To live-test, point `repo_url` at a sacrificial test repo, set `GITHUB_INTEGRATION_ENABLED=true`, `GITHUB_PUSH_ENABLED=true`, `GITHUB_TOKEN=<scoped PAT>`.
- **PR review:** the trial review was created manually with `provider="manual"`. Kody/Kody-style automated review was not exercised (no `KODY_REVIEW_ENABLED=true`).
- **Revision coding:** manual (Claude Code), recorded as additional commits through ForgeLoop. No tool run was generated for the revision because the OpenHands path requires `dev_task` scope, not `revision_work_item`. (Not a blocker — the revision's evidence chain is feedback → revision_work_item → commits → check_run → feedback resolution.)

## Cost Notes

- **LLM provider used:** `mock` only. Both `RequirementAnalysisAgent` and `TaskDecompositionAgent` and the memory-learning run all used the deterministic mock provider.
- **Estimated cost:** $0.
- **Real paid models used:** none.

## Lessons Learned

### What worked

- Backend-only end-to-end loop runs cleanly with `LLM_PROVIDER=mock` + `REPOSITORY_PROVIDER=memory` — no GCP, no external APIs, no network.
- Workspace registration with `local_existing` + an absolute `root_path` works exactly as described; the `pathlib`-only inspector correctly identified the trial as a git repo, counted files, and surfaced `.git/` as a blocked path hit (because I had added `.git/` to safety blocked paths — defensive but redundant given Task 37's built-in protections).
- The command runner produced real `command_run_output` artifacts under the safe sandbox (`shell=False`, PATH only).
- `CheckDefinition.command` was parsed with `shlex` and mapped 1:1 to a `CommandRun`; the linked `CheckRun.command_run_id` made it easy to trace evidence.
- Local git workflow (Task 37) really executed `git switch -c`, `git add`, and `git -c user.name=ForgeLoop -c user.email=forgeloop@local commit` on disk. Two commits landed, both verifiable with `git log`.
- The review feedback / revision work item lifecycle is strict but predictable: the only hiccup was needing a separate `revision_work_item` approval row for `proposed → approved`.
- Memory learning with the mock provider returned 2 candidates; both approve and reject paths worked.
- The audit trail captured every meaningful action. 69 events is a healthy density for the steps performed.

### What failed (or was not actually exercised)

- OpenHands live execution and GitHub draft PR creation were not exercised — both are intentionally feature-gated and correctly refused requests.
- Frontend smoke is not applicable: `apps/web` does not exist in this checkout despite being described in `CLAUDE.md`.
- Mock LLM output for task decomposition created a non-sensical task dependency (Issue #1) that I had to patch via PATCH.
- Approval API does not reject empty `target_id` (Issue #2). Easy authoring bug to make from a shell client.
- Docs say `GITHUB_INTEGRATION_ENABLED` is the first gate; in practice the repo-provider check fires first (Issue #3).
- Workspace hygiene: `.DS_Store` slipped into a commit (Issue #4).

### What should improve before using ForgeLoop for the first real project

1. **Tighten `ApprovalCreate` validation** (Issue #2). A real client should not be able to create unmatchable approvals.
2. **Add a tiny "workspace baseline `.gitignore`" guidance and/or built-in OS-noise blocklist** in Task 37's commit-path validator (Issue #4).
3. **Pick a side on the GitHub gate order and align docs vs. code** (Issue #3).
4. **Decide how revision implementations get a `ToolRun`.** Today the OpenHands prepare/execute endpoints scope on `dev_task` only. For a revision, the audit chain is via the revision_work_item + commit; that's coherent, but if OpenHands is expected to do revisions autonomously a `revision_work_item`-scoped execute would be cleaner.
5. **Recommend running ForgeLoop with an explicit absolute `FORGELOOP_WORKSPACE_ROOT`** — the default `./.forgeloop/workspaces` is relative to the backend's CWD (where `services/api/` is most natural), which is *not* the repo root, so workspaces can land in surprising places (60 prior UUID-named workspaces are sitting under `services/api/.forgeloop/workspaces/` from previous runs).
6. **Make the mock task decomposition's dependency direction realistic, or empty** (Issue #1).

## Final Recommendation

**Ready with manual fallback.** ForgeLoop is usable as a project-building control plane today for the local-only loop (workspace + branch + command + check + commit + PR draft + review + feedback + revision + memory). The two integrations that still require operator setup before they can be claimed as "validated" are OpenHands live execution and GitHub draft PR creation. None of the issues found above are blockers; #2 and #3 are worth a tiny follow-up. No ForgeLoop source-code changes were made during this trial.
