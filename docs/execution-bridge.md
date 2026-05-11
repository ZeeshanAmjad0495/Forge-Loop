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

## What comes next

- **Task 34 — Safe command runner.** Will introduce controlled command execution against a workspace, with allowlists, work-safe rules, and audit trails. Not part of Task 33.

Anything beyond Task 33 requires an explicit approved task.
