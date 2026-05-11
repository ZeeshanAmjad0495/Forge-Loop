# ForgeLoop Execution Bridge

The Execution Bridge is the layer that lets ForgeLoop act on a real local project workspace. It is being built additively after the core 32-task roadmap, one task at a time, with strict safety bounds.

## Task 33 — Local Workspace Manager (implemented)

Adds a safe local workspace abstraction so ForgeLoop can register, create, inspect, and archive controlled local project workspaces.

Backend additions:

- `Workspace` model (`services/api/app/models/workspaces.py`)
- `WorkspaceInspection` response shape (response-only, not persisted)
- `WorkspaceRepository` (memory + Firestore) wired through the standard `Repositories` container
- `WorkspaceService` (`services/api/app/services/workspaces.py`) — orchestrates create, register, update, inspect, archive
- `workspace_paths` helper (`services/api/app/services/workspace_paths.py`) — `pathlib`-only path safety and inspection
- Routes mounted at:
  - `POST   /projects/{project_id}/workspaces`
  - `GET    /projects/{project_id}/workspaces`
  - `GET    /workspaces/{workspace_id}`
  - `PATCH  /workspaces/{workspace_id}`
  - `POST   /workspaces/{workspace_id}/inspect`
  - `POST   /workspaces/{workspace_id}/archive`
- Audit actions: `workspace_created`, `workspace_registered`, `workspace_inspected`, `workspace_archived`, `workspace_invalid`

Frontend additions:

- `apps/web/src/types/workspaces.ts`
- `apps/web/src/api/workspaces.ts`
- `apps/web/src/components/panels/WorkspacesPanel.tsx` wired into `ProjectView`

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `FORGELOOP_WORKSPACE_ROOT` | `./.forgeloop/workspaces` | All locally-created workspaces live under this root |
| `WORKSPACE_ALLOW_OUTSIDE_ROOT` | `false` | When `false`, registered paths must be under the workspace root |

## Path safety rules

All paths go through `validate_and_resolve_path`:

1. `Path(raw).expanduser().resolve()` — collapses any `..` traversal.
2. Reject exact-match dangerous targets: `/`, `/etc`, `/usr`, `/var`, `/bin`, `/sbin`, the user's home directory, and the resolved CWD.
3. When `WORKSPACE_ALLOW_OUTSIDE_ROOT` is `false`, require the resolved path to be relative to the configured workspace root.

Workspace inspection uses **pathlib only**: `path.exists()`, `path.is_dir()`, `(path/".git").exists()`, and a bounded `os.scandir` walk (≤ 1000 entries). It does not read file contents and does not invoke `git`.

## Explicit non-goals (Task 33)

- No shell execution from the backend
- No `git` invocation (no `git status`, no branch, no clone, no commit)
- No GitHub / GitLab / Bitbucket API calls
- No PR creation
- No OpenHands or other coding-tool execution
- No source-file mutation (only empty-directory creation when explicitly approved)
- No remote repository cloning (`git_clone_pending` is metadata-only)
- No terminal or log streaming
- No Docker workspace execution
- No directory deletion (archive flips status only)

## Task 34 — Safe Command Runner foundation (implemented)

Adds workspace-scoped, allowlist-based local command execution so later tasks (CheckDefinition execution, OpenHands handoff, git/PR workflow) can dispatch tests/builds/lints inside a controlled workspace. **Disabled by default.**

Backend additions:

- `CommandDefinition` and `CommandRun` models (`services/api/app/models/commands.py`).
- `CommandDefinitionRepository` and `CommandRunRepository` (memory + Firestore) wired through the standard `Repositories` container.
- `CommandRunnerService` (`services/api/app/services/command_runner.py`) — validates, executes (`shell=False`), enforces timeout + output cap, writes audit + artifact records.
- Routes mounted at:
  - `POST   /projects/{project_id}/command-definitions`
  - `GET    /projects/{project_id}/command-definitions`
  - `GET    /command-definitions/{command_definition_id}`
  - `PATCH  /command-definitions/{command_definition_id}`
  - `POST   /workspaces/{workspace_id}/command-runs`
  - `GET    /workspaces/{workspace_id}/command-runs`
  - `GET    /projects/{project_id}/command-runs`
  - `GET    /command-runs/{command_run_id}`
- Audit actions: `command_definition_created`, `command_definition_updated`, `command_run_requested`, `command_run_blocked`, `command_run_completed`, `command_run_failed`, `command_run_timed_out`.
- Artifact type: `command_run_output` (saved when stdout/stderr is non-empty).

Frontend additions:

- `apps/web/src/types/commands.ts`
- `apps/web/src/api/commands.ts`
- `apps/web/src/components/panels/CommandRunnerPanel.tsx`, wired into `ProjectView` below the workspaces panel.

### Configuration (Task 34)

| Env var | Default | Purpose |
|---|---|---|
| `COMMAND_RUNNER_ENABLED` | `false` | Master kill switch. When `false`, run requests return `403` and nothing is executed. |
| `COMMAND_RUNNER_MAX_TIMEOUT_SECONDS` | `300` | Hard cap applied to every definition and run. |
| `COMMAND_RUNNER_MAX_OUTPUT_BYTES` | `200000` | Total combined stdout+stderr cap; each stream is truncated to half this. |
| `COMMAND_RUNNER_ALLOWED_COMMANDS` | `python,python3,pytest,npm,node,npx,ruff,mypy` | Executable allowlist. |
| `COMMAND_RUNNER_BLOCKED_COMMANDS` | `sudo,su,rm,rmdir,chmod,chown,curl,wget,ssh,scp,rsync,git,gh,docker,docker-compose,terraform,kubectl,gcloud,aws,az,openhands,aider,cline,opencode` | Explicit denylist. Takes precedence over the allowlist. |

### Safety policy

The command runner enforces every rule below in order:

1. `COMMAND_RUNNER_ENABLED` must be `true`; otherwise `403`.
2. Workspace must exist and be in `ready` or `registered` status.
3. If a `command_definition_id` is provided, the definition must exist, belong to the same project, be enabled, and (if bound) match the target workspace.
4. The executable must be in the allowlist and must not be in the blocklist.
5. `command` must be an executable name only — no path separators, no whitespace, no shell metacharacters.
6. Every `args` entry is re-checked for shell metacharacters: `|`, `&&`, `||`, `;`, `>`, `>>`, `<`, `$(`, backtick, newline.
7. `working_directory` (if provided) must be relative, must not contain `..`, must resolve to an existing directory inside the workspace root.
8. Execution uses `subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=…, shell=False, env={"PATH": …})`. No shell. No inherited secrets. PATH only.
9. `TimeoutExpired` becomes `status=timed_out / conclusion=timed_out`.
10. `OSError` / `FileNotFoundError` become `status=failed / conclusion=failure`.
11. stdout / stderr are truncated to the per-stream cap with a `…[truncated]` marker; an Artifact (`command_run_output`) is saved when output is non-empty and linked via `command_run.artifact_id`.
12. Every requested / blocked / completed / failed / timed-out run produces an audit event.

### Explicit non-goals (Task 34)

- No CheckDefinition → CommandDefinition auto-execution (Task 35).
- No OpenHands invocation (Task 36).
- No `git` / branch workflow (Task 37) — `git` is on the default blocklist.
- No GitHub PR creation (Task 38).
- No remote / Docker / CI / cloud execution.
- No terminal or log streaming.
- No ad-hoc free-text shell input in the UI.
- No cancel endpoint for in-flight runs.
- No environment-variable / secret injection into child processes.

## Task 35 — Actual Check Execution (implemented)

Connects approved `CheckDefinition`s to the Safe Command Runner so a deterministic check can be executed inside a registered workspace and recorded as a linked `CheckRun` + `CommandRun` pair.

Backend additions:

- `CheckRun.command_run_id` — optional pointer to the underlying `CommandRun` (additive, back-compat).
- `CheckExecutionRequest` / `CheckExecutionResponse` models (`services/api/app/models/checks.py`).
- `CheckExecutionService` (`services/api/app/services/check_execution.py`) — orchestrates validation, command parsing, delegation to `CommandRunnerService.run`, and CheckRun mapping. Never spawns subprocesses itself.
- Route mounted at:
  - `POST /check-definitions/{check_definition_id}/execute`
- Audit actions: `check_execution_requested`, `check_execution_completed`, `check_execution_failed`, `check_execution_blocked`.

Frontend additions:

- `executeCheckDefinition` in `apps/web/src/api/checks.ts`.
- `CheckExecutionRequest` / `CheckExecutionResponse` and `CheckRun.command_run_id` in `apps/web/src/types/checks.ts`.
- `ChecksPanel` (`apps/web/src/components/panels/CheckRunsPanel.tsx`) gains a workspace picker and per-definition Execute button; surfaces the linked CommandRun's status, conclusion, exit code, and output summary.

### Command parsing

`CheckDefinition.command` is split with `shlex.split(posix=True)` into an executable + args list. Each token is re-validated against the same shell-metacharacter rules the `CommandDefinition` validators apply. Anything ambiguous or unsafe is rejected with `400`.

Examples that parse safely:

| Command string | Executable | Args |
|---|---|---|
| `pytest` | `pytest` | `[]` |
| `pytest -q` | `pytest` | `["-q"]` |
| `npm run build` | `npm` | `["run", "build"]` |
| `python -m pytest` | `python` | `["-m", "pytest"]` |

Anything with `&&`, `|`, `;`, `>`, backticks, or `$()` is rejected at parse time.

### CommandRun → CheckRun mapping

| `CommandRun.conclusion` | `CheckRun.status` | `CheckRun.conclusion` |
|---|---|---|
| `success` | `completed` | `success` |
| `failure` | `failed` | `failure` |
| `timed_out` | `failed` | `failure` (summary notes the timeout) |
| `blocked` | `failed` | `failure` (summary starts with `Blocked:`) |

No new `CheckRun` enum values are introduced — the existing `pending|running|completed|failed` / `success|failure|neutral|skipped|cancelled` enums are preserved. The exact runner outcome is always available via `CheckRun.command_run_id`.

### Artifact behaviour

`CheckRun.artifact_id` is set to the underlying `CommandRun.artifact_id` (the `command_run_output` artifact already written by the runner). No duplicate artifact is created for the CheckRun.

### Status codes

| Status | When |
|---|---|
| `201` | Any terminal outcome (success, failure, timeout, blocked) — both records are returned in the body |
| `400` | Disabled definition; empty command; unsafe parse; workspace/project mismatch; workspace/repo mismatch |
| `403` | `COMMAND_RUNNER_ENABLED=false` |
| `404` | CheckDefinition or Workspace missing |

### Explicit non-goals (Task 35)

- No batch / "execute-all-required" endpoint — single-check execution only.
- No OpenHands invocation.
- No `git` / branch workflow; no GitHub PR creation.
- No arbitrary shell strings — only the parsed, validated CheckDefinition command runs.
- No new `CheckRun` enum values (`timed_out`, `blocked` map to existing `failed/failure`).
- No terminal / log streaming.
- No Docker / remote / CI execution.

## Task 36 — OpenHands local execution

Task 36 promotes the OpenHands runner from instruction-package-only to a
**controlled local execution mode**. It is disabled by default, workspace-scoped,
approval-gated, audited, output- and timeout-bounded, and does not invoke git,
GitHub, deploy, merge, or any branch/PR workflow.

### Endpoint

`POST /dev-tasks/{dev_task_id}/openhands/execute`

```jsonc
{
  "workspace_id": "ws-...",
  "tool_runner_definition_id": null,         // optional
  "approval_id": null,                       // optional; otherwise an approval is required
  "mode": "local",                           // "dry_run" | "local"
  "timeout_seconds": 900                     // capped by OPENHANDS_EXECUTION_HARD_CAP_SECONDS
}
```

Response: `{ tool_run, instruction_package, execution_summary }`. The summary
carries `exit_code`, `timed_out`, `duration_seconds`, `changed_paths`,
`blocked_path_changes`, `stdout_tail`, `stderr_tail`, `snapshot_truncated`.

`mode=dry_run` reuses the existing prepare flow — no executor invocation.
`mode=local` requires every gate below.

### Config (all default-safe)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENHANDS_EXECUTION_ENABLED` | `false` | Master kill switch. `false` ⇒ HTTP `409 OPENHANDS_EXECUTION_DISABLED`. |
| `OPENHANDS_COMMAND` | `""` | CLI binary; empty ⇒ `409 OPENHANDS_COMMAND_NOT_CONFIGURED`. |
| `OPENHANDS_ALLOWED_ARGS` | `[]` | Server-side argv template (e.g. `--instruction-file,{instruction_file}`). Request body cannot influence argv. |
| `OPENHANDS_TIMEOUT_SECONDS` | `1800` | Default timeout. |
| `OPENHANDS_EXECUTION_HARD_CAP_SECONDS` | `3600` | Caps both default and per-request timeouts. |
| `OPENHANDS_MAX_OUTPUT_BYTES` | `200000` | Combined stdout+stderr cap. |

### Safety profile

- `cwd` is `workspace.root_path` only. Workspace must be in `ready` status.
- `subprocess.run(shell=False, env={"PATH": …})`. No git, no gh, no docker, no
  cloud CLI invocation by ForgeLoop.
- Approval gate matches the `dev_tasks` ready transition: an approved
  approval on `dev_task` or its `task_decomposition` is required, or an
  explicit `approval_id` matching one of those.
- Before/after **metadata-only** filesystem snapshots produce a `changed_paths`
  summary (no file contents, no git). `.git`, `node_modules`, `.venv`, `dist`,
  `build`, `__pycache__`, `.pytest_cache`, `.forgeloop` are excluded.
- Safety-profile `blocked_paths` are checked against the diff. Any blocked
  write ⇒ `ToolRun.status=failed, conclusion=requires_human_action` and
  `openhands_execution_blocked` audit.

### ToolRun outcome mapping

| Outcome | status | conclusion | Audit |
|---------|--------|------------|-------|
| exit 0, no blocked paths | `completed` | `requires_human_action` | `openhands_execution_completed` |
| exit non-zero | `failed` | `failure` | `openhands_execution_failed` |
| timeout | `failed` | `failure` | `openhands_execution_timed_out` |
| executor error | `failed` | `failure` | `openhands_execution_failed` |
| blocked-path change | `failed` | `requires_human_action` | `openhands_execution_blocked` |
| flag/command disabled | no ToolRun, `409` | — | — |

`completed` runs default to `requires_human_action`: a human **must** review
the diff because there is no branch/PR workflow yet.

### Artifacts

- `openhands_instruction_package` — JSON package handed to OpenHands.
- `openhands_execution_output` — capped stdout/stderr bundle.
- `openhands_execution_changed_paths` — JSON diff summary (linked from
  `ToolRun.artifact_id`).

### Explicit non-goals (Task 36)

- No git invocation, no branch creation, no `gh`, no PR.
- No deploy, no merge.
- No arbitrary shell input (argv is server-side only).
- No terminal / log streaming.
- No Docker orchestration, no CI provider integration.
- No subtask-scoped execute endpoint.
- No new `ToolRun` status/conclusion values — outcomes map within the existing
  enum and use a dedicated audit action for `timed_out`/`blocked` clarity.

## Task 37 — Local git branch workflow

Task 37 adds a **narrow, local-only** git capability: ForgeLoop can inspect
git state inside a registered workspace, create ForgeLoop-scoped local
branches, and (when explicitly enabled and approved) make local commits.
**Nothing is pushed.** No remote fetch, no merge, no rebase, no reset, no
GitHub call. Task 38 will own remote push and PR creation; Task 37 just
produces the durable local branch + commit evidence Task 38 needs.

### Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/workspaces/{workspace_id}/git/inspect` | POST | Read-only git state for the workspace. |
| `/workspaces/{workspace_id}/branches` | POST | Create a ForgeLoop-scoped local branch. |
| `/workspaces/{workspace_id}/branches` | GET | List branches. |
| `/workspace-branches/{branch_id}` | GET | Branch record + fresh inspection. |
| `/workspace-branches/{branch_id}/inspect` | POST | Refresh branch record from current git state. |
| `/workspace-branches/{branch_id}/commit` | POST | Local commit (config + approval gated). |
| `/workspace-branches/{branch_id}/commits` | GET | List commit records on a branch. |

Disabled-state errors are HTTP `409` with detail `GIT_WORKFLOW_DISABLED` or
`GIT_COMMIT_DISABLED`.

### Config

| Variable | Default | Purpose |
|---|---|---|
| `GIT_WORKFLOW_ENABLED` | `false` | Master switch for branch creation. Inspection is always available. |
| `GIT_COMMIT_ENABLED` | `false` | Required for local commits. |
| `GIT_ALLOWED_BRANCH_PREFIX` | `forgeloop/` | Branch names must start with this. |
| `GIT_PROTECTED_BRANCHES` | `main,master,develop,production,release` | Comma-separated; rejected for branch creation. Unioned with the safety profile's `protected_branches`. |
| `GIT_TIMEOUT_SECONDS` | `60` | Per git invocation. |
| `GIT_MAX_DIFF_BYTES` | `200000` | Cap on captured output. |
| `GIT_COMMIT_MESSAGE_MAX_LEN` | `2000` | Commit message length cap. |
| `GIT_BINARY` | `git` | Override the git executable path. |

### Allowed git operations (the full set)

Task 37 ever invokes only these:

```
git rev-parse --is-inside-work-tree
git rev-parse --abbrev-ref HEAD
git rev-parse --verify --quiet refs/heads/<base>
git rev-parse HEAD
git status --porcelain=v1 --untracked-files=all
git diff --name-only HEAD
git diff --stat HEAD
git diff --stat HEAD~1..HEAD
git switch -c <safe forgeloop-scoped name>
git switch <safe forgeloop-scoped name>          # ensure HEAD before commit
git add -- <safe diff-set paths>
git -c user.name=ForgeLoop -c user.email=forgeloop@local commit -m <msg> --no-gpg-sign
```

Everything else — `push`, `pull`, `fetch`, `merge`, `rebase`, `reset`,
`clean`, `tag`, `remote`, `stash`, `worktree`, `cherry-pick`, arbitrary
`checkout` — is **never constructed** by ForgeLoop and is also explicitly
rejected by the `_run_git` argv allow-list (defense in depth).

### Safety profile

- Branch validator unions `GIT_PROTECTED_BRANCHES` with the safety profile's
  `protected_branches`.
- Commit-path validator unions the profile's `blocked_paths` with a built-in
  secrets blocklist (`.env*`, `id_rsa`/`id_dsa`/`id_ecdsa`/`id_ed25519`,
  `*.pem`, `*.key`, `*.p12`, `.aws/`, `.ssh/`, `secrets/`).
- Pre-commit hooks are not bypassed — if a repo's hooks fail, the commit
  fails and is recorded as `workspace_commit_failed`.
- Identity is per-invocation (`-c user.name=ForgeLoop -c user.email=forgeloop@local`);
  ForgeLoop never writes to `git config --global`.

### Records

- `WorkspaceBranch` — id, workspace, project, code_repository, optional
  dev_task / subtask / tool_run links, name, base_branch, current_branch,
  status (`prepared|active|clean|dirty|committed|failed|archived`).
- `GitCommitRecord` — id, workspace_branch_id, commit_sha, message,
  changed_files, capped diff_stat, status (`prepared|committed|failed`),
  optional `artifact_id` pointing to the commit summary artifact.

### Artifacts

- `git_inspection_summary` — JSON of inspection (no diff content).
- `git_commit_summary` — JSON of commit metadata + capped diff stat.

### Audit actions

`git_inspection_completed`, `workspace_branch_created`,
`workspace_branch_inspected`, `workspace_commit_prepared`,
`workspace_commit_created`, `workspace_commit_failed`,
`git_operation_blocked`.

### Explicit non-goals (Task 37)

- No push / pull / fetch / merge / rebase / reset / clean / stash / tag /
  remote / worktree / cherry-pick / arbitrary checkout.
- No GitHub call, no PR creation.
- No deploy, no monitoring/CI provider integration.
- No OpenHands invocation.
- No arbitrary git CLI input.
- No terminal/log streaming, no diff viewer.

## What comes next

- **Task 38 — GitHub PR creation.** Will use the `WorkspaceBranch` +
  `GitCommitRecord` produced here to push remote and open a PR.
- **Task 39 — Review feedback loop.**

Human review remains required between Tasks 36/37 and Tasks 38+. Anything
beyond Task 37 requires an explicit approved task.
