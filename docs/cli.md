# ForgeLoop CLI-first workflow (Task 84)

ForgeLoop is CLI-first. The CLI is standard-library only (no extra
dependencies) and is a thin wrapper over the HTTP API — every command
maps 1:1 to an endpoint, so the API stays the source of truth.

```bash
# from services/api
export FORGELOOP_API_URL=http://localhost:8080
python -m app.cli --help                 # all commands
python -m app.cli create-project --help  # per-command help
python -m app.cli <command> --dry-run    # print the request, send nothing
```

Global flags (`--dry-run`, `--token`, `--base-url`) work **either before
or after** the subcommand.

## Running the API locally

The CLI talks to a running API. With the default `AUTH_ENABLED=true`, the
API **fail-closes**: it refuses to start unless `AUTH_TOKEN_SECRET` is set
(>= 32 chars) — this is the correct secure default, not a bug. Options:

```bash
# A) auth on (recommended): export a random local secret, then login
export AUTH_TOKEN_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))")
# B) local dev, no auth (explicit opt-in only):
export ENVIRONMENT=local AUTH_ENABLED=false FORGELOOP_ALLOW_NO_AUTH=true
uv run uvicorn app.main:app --port 8080
```

## Auth

```bash
python -m app.cli login --email admin@example.com --password "$ADMIN_PW"
# copy the printed token:
export FORGELOOP_TOKEN=<access_token>
python -m app.cli whoami
```

## Core workflow

| Step | Command |
|------|---------|
| Create project | `python -m app.cli create-project --name Demo --description "..."` |
| Create ticket | `python -m app.cli create-ticket --project <pid> --title T --description D` |
| Create requirement | `python -m app.cli create-requirement --project <pid> --title T --description D` |
| Generate plan | `python -m app.cli generate-plan --ticket <tid> --provider mock` |
| Decompose into DevTasks | `python -m app.cli create-dev-tasks --ticket <tid>` |
| Request approval | `python -m app.cli request-approval --project <pid> --target-type task_decomposition --target-id <id>` |
| Decide approval | `python -m app.cli decide-approval --approval <aid> --status approved` |
| Show pending approvals | `python -m app.cli approvals --project <pid>` |
| Preview runner routing | `python -m app.cli runner-preview --project <pid>` |
| Preview model routing | `python -m app.cli model-route-preview --project <pid>` |
| Show provider usage / cost | `python -m app.cli cost --project <pid>` |
| Runtime posture | `python -m app.cli runtime --topic cache` (or `vector`, `workflow`, `observability`, `auto-remediation`, `model-routing`, `runner-routing`) |

## Warnings to watch (cost / approval / routing)

These surface in API responses and in the dashboard header legend:

- **Kimi blocked / approval required** — the expensive provider was
  gated by the budget guard (`model-route-preview` → `expensive_provider_blocked`).
- **Expensive provider usage** — a non-default provider was selected.
- **Runner approval required** — `runner-preview` →
  `requires_human_approval` (OpenHands / broad change).
- **Context reduction recommended** — a ContextPack exceeded its token
  budget (`context_exceeds_budget_after_reduction...` warning).

## Dashboard

The web app (`apps/web`) is intentionally minimal. The header now shows
the canonical pipeline (Project → Requirement/Ticket → Plan → DevTasks →
Runner/PR → Review → CI/Incident → Memory) and a collapsible legend of
the warnings above — enough for presentation/supervision without a
complex dashboard.
