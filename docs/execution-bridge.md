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

## What comes next

- **Task 35 — CheckDefinition execution.** Will let approved `CheckDefinition`s execute via the safe command runner.
- **Task 36 — OpenHands execution.** Adds the OpenHands handoff for code-change work.
- **Task 37 — git branch workflow.**
- **Task 38 — GitHub PR creation.**

Anything beyond Task 34 requires an explicit approved task.
