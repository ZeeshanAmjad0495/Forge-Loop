# IncidentPilot

> An agentic QAOps platform that generates implementation-ready planning briefs from software tickets.

## What IncidentPilot does (MVP)

1. Accept a ticket (title + description) via API or web UI.
2. Run a planning agent that calls an LLM to generate an implementation-ready brief in markdown.
3. Store tickets, agent runs, and artifacts — in memory locally or in Firestore on GCP.
4. Expose everything through a REST API and a minimal React frontend.

## What it does not do yet

- Create branches, commits, or pull requests autonomously
- Review pull requests
- Triage incidents or analyze production failures
- Integrate with GitHub, Slack, or any external ticketing system
- Authenticate users or enforce access control
- Support multiple tenants or billing

See [Future roadmap](#future-roadmap) for what comes next.

## Architecture summary

The backend is a FastAPI service running on Cloud Run. It receives tickets, orchestrates the planning agent, and stores results in Firestore. The frontend is a static React + Vite app that calls the API directly. Infrastructure is managed with Terraform. All agent output is for **human review** — nothing is merged or deployed autonomously.

See [docs/architecture.md](docs/architecture.md) for full details.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI | DeepSeek (mock provider by default — no key needed locally) |
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
| `LLM_PROVIDER` | `mock` | `mock` (no key) or `deepseek` |
| `LLM_MODEL` | _(provider default)_ | Model name passed to the provider |
| `DEEPSEEK_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=deepseek` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API endpoint |
| `GCP_PROJECT_ID` | _(empty)_ | Required when `REPOSITORY_PROVIDER=firestore` |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database name |

### Frontend (`apps/web/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8080` | Backend API base URL |

---

## LLM provider configuration

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

The `infra/terraform/` directory provisions the minimum GCP infrastructure needed to run IncidentPilot in production.

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

The following are **not implemented** in the current MVP:

- **PR review agent** — analyze pull request diffs and generate review notes
- **Incident triage agent** — analyze production failures and generate triage reports
- **Branch and task decomposition** — break briefs into subtasks and create branches
- **GitHub App integration** — trigger agents from GitHub events
- **Slack notifications** — post agent output to Slack channels
- **Authentication and RBAC** — user accounts, roles, organization scoping
- **Multi-tenancy and billing** — isolated workspaces per organization
- **Pub/Sub / Eventarc triggers** — event-driven agent execution
- **Frontend deployment** — Cloud Storage or Firebase Hosting for the web UI
- **Vector search / RAG** — retrieve relevant context for planning prompts
- **MCP server** — expose IncidentPilot tools to Claude or other agents
- **Multi-environment infrastructure** — dev/staging/prod Terraform workspaces
