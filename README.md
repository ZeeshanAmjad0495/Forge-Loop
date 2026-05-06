# ForgeLoop

> A human-supervised autonomous SDLC + STLC control plane. ForgeLoop orchestrates the full software delivery lifecycle — from requirements to production — coordinating AI agent runs, enforcing human approvals, and delegating code execution to existing tools.

The current release is the planning platform (Release 1) plus per-request provider selection (Release 2). Project memory, GitHub integration, tool-runner-driven coding, AI-assisted PR review, and incident triage are on the roadmap but **not yet implemented** — see [Future roadmap](#future-roadmap).

## What ForgeLoop does today (Releases 1 + 2)

1. Accept a ticket (title + description) via API or web UI.
2. Let the user choose which LLM provider drafts the planning brief (mock, DeepSeek, or Kimi).
3. Run a planning agent that calls the selected LLM to generate an implementation-ready brief in markdown.
4. Store tickets, agent runs, and artifacts — in memory locally or in Firestore on GCP.
5. Expose everything through a REST API and a minimal React frontend.

## What it does not do yet

- Track projects or project memory (architecture decisions, coding standards, prior feedback)
- Create branches, commits, or pull requests
- Review pull requests
- Run multiple planning candidates and pick the best
- Decompose approved briefs into dev tasks and subtasks
- Delegate execution to coding tools (OpenHands, Aider, Cline, OpenCode, Hermes Agent)
- Triage incidents or analyze production failures / CI failures
- Integrate with GitHub, Slack, or any external ticketing system
- Authenticate users or enforce access control
- Support multiple tenants or billing
- Generate marketing or product-growth artifacts

See [Future roadmap](#future-roadmap) for which release each item belongs to.

## Architecture summary

The backend is a FastAPI service running on Cloud Run. It receives tickets, orchestrates the planning agent (against a user-selectable LLM provider), and stores results in Firestore. The frontend is a static React + Vite app that calls the API directly. Infrastructure is managed with Terraform. All agent output is for **human review** — nothing is merged or deployed autonomously.

The longer-term target architecture (Releases 3–6) is project-centered: Project → ProjectMemory → Tickets → multi-candidate AgentRuns → Evaluator → Approved Brief → DevTasks → ToolRunner execution → Branch / PR → AI Review → Human Review → Merge. None of that is implemented yet.

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
| `REPOSITORY_PROVIDER` | `memory` | `memory` (local) or `firestore` (GCP) |
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
| `AUTH_TOKEN_SECRET` | _(empty)_ | Secret used to sign JWT tokens (min 32 bytes recommended) |
| `AUTH_TOKEN_TTL_SECONDS` | `86400` | Token validity period in seconds (default 24 h) |

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

ForgeLoop's long-term direction is a **human-supervised autonomous SDLC + STLC control plane** — it orchestrates the full software delivery lifecycle and delegates code execution to existing tools rather than reimplementing them from scratch. The active engineering scope is fixed at **32 tasks across 6 releases**. None of the items below are implemented yet unless explicitly noted.

### Release 1 — Planning Platform (Tasks 1–12) — Complete

Ticket creation, planning agent with mock provider, DeepSeek integration, Firestore persistence, Docker, CI, Cloud Run deployment, Terraform, minimal frontend, docs.

### Release 2 — Provider + Basic Usability (Tasks 13–15) — Complete

- Kimi (Moonshot) provider integration
- Per-request provider selection (`GET /llm/providers` + UI selector)
- Documentation alignment with product direction

### Release 3 — GitHub + Approval Foundation (Tasks 16–20)

- GitHub App or webhook integration (trigger agents from GitHub events)
- Branch creation
- PR creation
- Human approval gate workflow (explicit sign-off at each stage transition)
- Audit log (history of agent runs, evaluations, and human decisions)

### Release 4 — Tool-based Coding Automation (Tasks 21–25)

- Tool runner abstraction (interface for invoking external coding tools)
- First tool runner integration (OpenHands or Aider; later Cline, OpenCode, Hermes Agent)
- Dev task decomposition (break approved briefs into actionable dev tasks)
- Multi-candidate orchestration (run multiple agents/prompts; evaluator selects)
- Change request loop (human requests revision; agent reruns against feedback)

### Release 5 — Review + CI Intelligence (Tasks 26–29)

- AI-assisted PR review (analyze diffs, generate structured review notes)
- CI failure analysis
- Test run evaluation
- Prompt version tracking (which prompt produced which artifact)

### Release 6 — IncidentOps (Tasks 30–32)

- Incident triage agent
- Production failure analysis
- Remediation brief workflow

### Release 7 — LaunchPilot / Marketing (Future, parked)

**Not part of the active 32-task roadmap.** This release is subsumed by LaunchPilot, a ForgeLoop Studio module. Plan separately after Release 6 is complete. Possible scope: landing page copy, product positioning, marketing campaign planner, social post generator, cold outreach drafts, user feedback collector, competitor/research tracker.

### Always out of scope (for the current 32-task roadmap)

Pub/Sub/Eventarc, Kubernetes, Slack integration, authentication/RBAC, multi-tenancy/billing, complex dashboard, background workers, vector DB / RAG, MCP server, LangGraph (only adopt if a real need appears), long-running agent workflows.
