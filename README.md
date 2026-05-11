# ForgeLoop

> A human-supervised autonomous SDLC + STLC control plane. ForgeLoop orchestrates the full software delivery lifecycle — from requirements to production — coordinating AI agent runs, enforcing human approvals, and delegating code execution to existing tools.

All 32 core tasks across Releases 1–6 are complete. See [Future roadmap](#future-roadmap) for what comes next.

## What ForgeLoop does today (Releases 1–6)

1. Accept structured requirements or tickets via API or web UI.
2. Manage projects with project context and project memory (architecture decisions, standards, prior feedback).
3. Analyze requirements and generate clarification questions before planning.
4. Let the user choose which LLM provider drafts the planning brief (mock, DeepSeek, or Kimi).
5. Run a planning agent that calls the selected LLM to generate an implementation-ready brief in markdown.
6. Decompose approved briefs into dev tasks and subtasks with lifecycle management.
7. Enforce human approval gates at planning-to-task transitions.
8. Record audit events for agent runs, human decisions, and state transitions.
9. Store everything — in memory locally or in Firestore on GCP.
10. Expose it all through a REST API and a minimal React frontend.
11. Connect code repositories and enforce repo safety profiles (branch protection, no-force-push).
12. Run deterministic QA/security check definitions and record check runs (Semgrep, Trivy, OSV-Scanner, Gitleaks, axe-core, Playwright, native tests).
13. Trace LLM prompt versions, cost, and token usage per agent run via Langfuse.
14. Invoke external coding tools via the ToolRunner abstraction (OpenHandsRunner foundation; dry-run mode).
15. Track PR drafts (title/body from task output, human approval gate, paste-back of external PR URL).
16. Request and record AI-assisted PR reviews via Kodus/Kody (tracking + adapter foundation).
17. Ingest CI failure events and produce advisory LLM-assisted `CIAnalysis` records.
18. Record production incidents and produce advisory `IncidentAnalysis` triage reports; prepare non-persisted remediation work item drafts for human review.
19. Distill learnings from CI analyses, incident analyses, PR reviews, check runs, and dev tasks into `ProjectMemoryCandidate`s; human approve/reject writes them back into project context.

## What it does not do (by design)

- Create branches, commits, or pull requests autonomously
- Merge or deploy without explicit human approval
- Connect to live monitoring systems (Sentry, Datadog, Cloud Logging polling, OpenTelemetry)
- Auto-detect or auto-remediate incidents
- Send Slack, email, or PagerDuty notifications
- Integrate with GitHub webhooks or CI provider APIs directly
- Support multiple tenants or billing
- Generate marketing or product-growth artifacts (see LaunchPilot / Release 7)

> **API note:** Repo safety-profile updates use `PATCH /code-repositories/{id}/safety-profile` (not PUT).

See [Future roadmap](#future-roadmap) for planned next steps.

## Architecture summary

The backend is a FastAPI service running on Cloud Run. It receives tickets, orchestrates the planning agent (against a user-selectable LLM provider), and stores results in Firestore. The frontend is a static React + Vite app that calls the API directly. Infrastructure is managed with Terraform. All agent output is for **human review** — nothing is merged or deployed autonomously.

The full delivery pipeline is now implemented through Release 6: Requirements → Planning Brief → DevTasks → ToolRunner (OpenHands, dry-run) → PR Draft → Kodus/Kody Review → Human Approval → Merge. CI failure ingestion, incident triage, and the project memory learning loop are also live. Nothing is merged or deployed autonomously.

See [docs/architecture.md](docs/architecture.md) for full details.

---

## ForgeLoop vs ForgeLoop Studio

**ForgeLoop** (this repo) is the current product being built. It is a human-supervised SDLC + STLC control plane that converts requirements into planning briefs, tasks, code, QA, PRs, reviews, and deployments.

**ForgeLoop Studio** is the broader future vision — an AI-native product factory of which ForgeLoop is the core engine. It consists of four modules:

| Module | Role | Status |
|--------|------|--------|
| **ProductScout** | Market research and product discovery. Outputs structured requirements that feed into ForgeLoop. | Not implemented |
| **ForgeLoop** | This repo. Engineering control plane — planning through deployment. | Active build |
| **AuditLens** | Independent software auditor (security, compliance, UX, performance). Creates improvement tickets back into ForgeLoop. | Not implemented |
| **LaunchPilot** | Marketing and sales support. Landing pages, positioning, outreach, client requirement intake. | Not implemented (parked) |

**This repo contains ForgeLoop core only.** ProductScout, AuditLens, and LaunchPilot are not implemented here. The active engineering roadmap covers ForgeLoop Releases 1–6 (32 tasks).

See [docs/architecture.md — ForgeLoop Studio](docs/architecture.md#forgeloop-studio-future-vision) for the full flow and shared data model.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI | Mock (default), DeepSeek, Kimi (Moonshot) — provider-agnostic, selectable per request |
| Persistence | In-memory (local/tests) · Firestore native mode (cloud) |
| Frontend | React 18, Vite, TypeScript |
| Container | Docker (python:3.12-slim), port 8080 |
| Cloud | Google Cloud Run, Artifact Registry, Firestore, Secret Manager |
| Infrastructure | Terraform (google provider ~> 5.0) |
| CI/CD | GitHub Actions + Workload Identity Federation |

## Repository structure

```
incidentpilot/
├── .github/
│   └── workflows/
│       ├── api-ci.yml       # CI: test + build on PR
│       └── api-deploy.yml   # CD: build + push + deploy on merge to main
├── apps/
│   └── web/                 # React + Vite frontend
│       ├── src/
│       │   ├── App.tsx
│       │   ├── api.ts
│       │   └── types.ts
│       ├── package.json
│       └── .env.example
├── docs/
│   ├── architecture.md
│   ├── demo-flow.md
│   └── sample-ticket.md
├── infra/
│   └── terraform/           # GCP infrastructure
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── versions.tf
├── services/
│   └── api/                 # FastAPI backend
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── models.py
│       │   ├── repositories.py
│       │   ├── planning_agent.py
│       │   └── llm/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
└── README.md
```

---

## Local setup — backend

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` as needed (defaults use mock LLM and in-memory storage — no GCP credentials required).

### Start the backend

```bash
uvicorn app.main:app --port 8080 --reload
```

API is available at `http://localhost:8080`. Interactive docs at `http://localhost:8080/docs`.

## Running backend tests

```bash
cd services/api
pytest
```

All tests run without GCP credentials or a real LLM key.

---

## Local setup — frontend

```bash
cd apps/web
npm install
cp .env.example .env
```

### Start the frontend dev server

```bash
npm run dev
```

Opens at `http://localhost:5173`. Requires the backend to be running on `:8080` (or set `VITE_API_BASE_URL` in `.env`).

### Build for production

```bash
npm run build   # outputs to dist/
```

---

## Running Docker locally

```bash
cd services/api
docker build -t incidentpilot-api .
docker run -p 8080:8080 incidentpilot-api
```

Pass environment variables with `-e` or `--env-file .env`.

---

## Environment variables

### Backend (`services/api/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | Runtime environment label |
| `REPOSITORY_PROVIDER` | `memory` | `memory` (local/tests), `local_document` (durable local MongoDB), or `firestore` (GCP) |
| `LOCAL_DOCUMENT_DB_PROVIDER` | `mongodb` | Backend for `local_document`. Currently only `mongodb`. |
| `MONGODB_URI` | `mongodb://localhost:27017` | Connection URI used when `REPOSITORY_PROVIDER=local_document` |
| `MONGODB_DATABASE` | `forgeloop_local` | Database name used by the local document provider |
| `MONGODB_CONNECT_TIMEOUT_MS` | `3000` | Mongo connect timeout (ms) |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | `3000` | Mongo server-selection timeout (ms) |
| `LLM_PROVIDER` | `mock` | Default provider — `mock` (no key), `deepseek`, or `kimi`. Can be overridden per request from the UI. |
| `LLM_MODEL` | _(provider default)_ | Model name passed to the provider |
| `DEEPSEEK_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=deepseek` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API endpoint |
| `KIMI_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=kimi` |
| `KIMI_BASE_URL` | `https://api.moonshot.ai/v1` | Kimi API endpoint |
| `GCP_PROJECT_ID` | _(empty)_ | Required when `REPOSITORY_PROVIDER=firestore` |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database name |
| `AUTH_ENABLED` | `true` | Set `false` to disable auth (local dev / tests only) |
| `AUTH_ADMIN_EMAIL` | _(empty)_ | Admin login email |
| `AUTH_ADMIN_PASSWORD` | _(empty)_ | Admin login password |
| `AUTH_TOKEN_SECRET` | _(empty)_ | **Required when `AUTH_ENABLED=true`.** Secret used to sign JWT tokens (min 32 chars). Fails fast at startup if missing. |
| `AUTH_TOKEN_TTL_SECONDS` | `86400` | Token validity period in seconds (default 24 h) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed CORS origins. No wildcard default. Add your deployed frontend URL for cloud deployments. |

### Frontend (`apps/web/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8080` | Backend API base URL |

---

## LLM provider configuration

Three providers are implemented: **mock** (default), **DeepSeek**, and **Kimi (Moonshot)**. The `LLM_PROVIDER` env var sets the default; the frontend lets the user pick a configured provider per planning run. `GET /llm/providers` reports which providers are configured (without exposing keys).

**Mock (default):** No API key required. Returns a hardcoded implementation brief template. Used automatically in all automated tests.

```bash
LLM_PROVIDER=mock
```

**DeepSeek:** Calls the real DeepSeek API. Requires an API key.

```bash
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-...
```

**Kimi (Moonshot):** Calls the Kimi API. Requires an API key from [platform.moonshot.cn](https://platform.moonshot.cn).

```bash
LLM_PROVIDER=kimi
LLM_MODEL=kimi-k2.6
KIMI_API_KEY=sk-...
```

---

## Auth configuration

Auth is **enabled by default** (`AUTH_ENABLED=true`). Set it to `false` only for local development without credentials or for automated tests.

Single admin user — set these before running:

```bash
AUTH_ADMIN_EMAIL=admin@example.com
AUTH_ADMIN_PASSWORD=your-strong-password
AUTH_TOKEN_SECRET=$(openssl rand -hex 32)
```

The frontend shows a login screen when no token is stored. On successful login the backend returns a signed JWT (24 h TTL by default) which the frontend stores in `localStorage`.

**Cloud Run / production:** `AUTH_TOKEN_SECRET` and `AUTH_ADMIN_PASSWORD` should be stored in Secret Manager and mounted as env vars on the Cloud Run service (same pattern as `DEEPSEEK_API_KEY`). Not automated by Terraform yet — follow-up task.

---

## Firestore configuration

**Local / tests:** Default `REPOSITORY_PROVIDER=memory` uses in-memory storage. No GCP setup needed.

**Cloud Run:** Set these on the Cloud Run service (Terraform wires them automatically):

```bash
REPOSITORY_PROVIDER=firestore
GCP_PROJECT_ID=your-project-id
FIRESTORE_DATABASE=(default)
```

The runtime service account needs `roles/datastore.user` on the project (handled by Terraform).

---

## Local durable mode (MongoDB)

For single-developer use with persistence across backend restarts — without depending on GCP — point ForgeLoop at a local MongoDB:

```bash
REPOSITORY_PROVIDER=local_document
LOCAL_DOCUMENT_DB_PROVIDER=mongodb
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=forgeloop_local
```

Install the optional dependency once:

```bash
pip install -e 'services/api[local_document]'
```

Start MongoDB with the bundled compose file (or use any local `mongod` install):

```bash
docker compose -f services/api/docker-compose.local.yml up -d mongodb
```

Verify durability end-to-end:

1. Start the backend with the env vars above.
2. `POST /projects` — create a project.
3. Restart the backend.
4. `GET /projects/{id}` — the project is still there.

If MongoDB is unreachable when `REPOSITORY_PROVIDER=local_document`, the backend fails fast at startup with a redacted-URI error — it never silently falls back to in-memory.

The `memory` and `firestore` providers are unchanged and remain the defaults for tests and Cloud Run respectively. `pymongo` is only imported when `local_document` is selected.

---

## Terraform

The `infra/terraform/` directory provisions the minimum GCP infrastructure needed to run ForgeLoop in production.

**Resources created:**
- Artifact Registry (Docker repository)
- Firestore native-mode database
- Cloud Run service (initially with a placeholder image)
- Runtime service account + IAM bindings
- Secret Manager secret for the DeepSeek API key

**First-time setup:**

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set project_id to your GCP project
terraform init
terraform plan -var="project_id=YOUR_PROJECT"
terraform apply -var="project_id=YOUR_PROJECT"
```

After apply, add the DeepSeek API key to Secret Manager:

```bash
printf "sk-your-real-key" | gcloud secrets versions add \
  incidentpilot-deepseek-api-key --data-file=- --project=YOUR_PROJECT
```

`terraform apply` is **not** run by GitHub Actions — infrastructure changes are operator-managed.

---

## GitHub Actions

**CI (`api-ci.yml`):** Runs on every pull request that touches `services/api/`.
- Installs dependencies
- Runs `pytest`
- Builds the Docker image

**Deploy (`api-deploy.yml`):** Runs on merge to `main` when `services/api/`, `infra/terraform/`, or the workflow file changes.
- Authenticates to GCP via Workload Identity Federation (no JSON keys)
- Builds and pushes the Docker image to Artifact Registry
- Deploys the new image to Cloud Run

---

## Deployment

Merges to `main` trigger the deploy workflow automatically.

### Required GitHub Actions configuration

Set these in **GitHub → repo settings → Secrets and variables → Actions**:

**Variables** (non-sensitive):

| Name | Example |
|------|---------|
| `GCP_PROJECT_ID` | `incidentpilot-prod` |
| `GCP_REGION` | `us-central1` |
| `ARTIFACT_REGISTRY_REPOSITORY` | `incidentpilot` |
| `CLOUD_RUN_SERVICE` | `incidentpilot-api` |

**Secrets** (masked in logs):

| Name | Description |
|------|-------------|
| `WIF_PROVIDER` | Workload Identity Federation provider resource path |
| `WIF_SERVICE_ACCOUNT` | Deployer service account email |

The WIF pool/provider and deployer SA are operator-managed prerequisites — they are not created by the Terraform in this repo. The deployer SA needs `roles/artifactregistry.writer`, `roles/run.admin`, and `roles/iam.serviceAccountUser` on the runtime SA.

### Public access

The Cloud Run service is **private by default**. To allow unauthenticated access, add this resource to `infra/terraform/main.tf` and re-apply:

```hcl
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

---

## Demo workflow

See [docs/demo-flow.md](docs/demo-flow.md) for a step-by-step local demo.

---

## Future roadmap

ForgeLoop's long-term direction is a **human-supervised autonomous SDLC + STLC control plane**. The active engineering scope of **32 tasks across 6 releases is now complete**.

### Release 1 — Planning Platform (Tasks 1–12) — Complete

Ticket creation, planning agent with mock provider, DeepSeek integration, Firestore persistence, Docker, CI, Cloud Run deployment, Terraform, minimal frontend, docs.

### Release 2 — Provider + Basic Usability (Tasks 13–16) — Complete

- Kimi (Moonshot) provider integration
- Per-request provider selection (`GET /llm/providers` + UI selector)
- Auth/login (JWT, single admin user)
- Project-aware dashboard + project context/memory

### Release 3 — Requirements + Task Planning Engine (Tasks 17–21) — Complete

- Structured requirements intake (not just free-text tickets)
- Requirement analysis and clarification questions
- Task/subtask decomposition from approved planning briefs
- Task lifecycle management (status tracking, sequencing, dependencies)
- Human approval gates at planning-to-task transitions
- Audit event foundation (agent run history, human decisions)

### Release 4 — Golden Path + Deterministic QA (Tasks 22–25) — Complete

- Repo connection + repo safety profile (branch protection awareness, no-force-push rules)
- Deterministic QA/security bundle: Semgrep, OSV-Scanner, Trivy, Gitleaks, axe-core, native test/coverage tools
- Playwright / browser QA lane (Playwright Test Agents as primary E2E tool)
- Langfuse tracing: prompt versions, cost records, token usage per agent run

### Release 5 — Tool Runner + PR Workflow (Tasks 26–29) — Complete

- ToolRunner abstraction (single interface for invoking external coding tools)
- OpenHandsRunner as the primary coding runner (foundation; dry-run mode)
- PR draft workflow (task output → PR draft tracking, human approval gate)
- Kodus/Kody PR review integration (tracking + adapter foundation)

### Release 6 — CI + Incident + Learning Loop (Tasks 30–32) — Complete

- CI failure ingestion and advisory LLM analysis
- Production/incident ticket workflow (manual ingestion → triage → advisory remediation draft)
- Project memory learning loop (human-supervised candidate distillation and approval)

### Release 7 — LaunchPilot / Marketing (Future, parked)

**Not part of the active 32-task roadmap.** Subsumed by LaunchPilot, a ForgeLoop Studio module. Plan separately. Possible scope: landing page copy, product positioning, marketing campaign planner, social post generator, cold outreach drafts.

### Always out of scope

Pub/Sub/Eventarc, Kubernetes, live monitoring integration, auto-remediation, Slack/email notifications, multi-tenancy/billing, complex dashboard, background workers, vector DB / RAG, MCP server, Temporal/Kestra/LangGraph.
