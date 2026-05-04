# Demo Flow

Step-by-step guide to running IncidentPilot locally and generating a planning brief.

## Prerequisites

- Python 3.12+
- Node.js 18+
- A DeepSeek API key — **or** use the mock provider (no key needed)

---

## Step 1: Start the backend

```bash
cd services/api

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
```

To use the **mock provider** (instant response, no key needed), leave `.env` as-is.

To use the **real DeepSeek provider**, edit `.env`:
```
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-your-real-key
```

Start the server:
```bash
uvicorn app.main:app --port 8080 --reload
```

Verify: `curl http://localhost:8080/health` should return `{"status":"ok","service":"incidentpilot-api"}`.

---

## Step 2: Start the frontend

In a separate terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173` in a browser.

---

## Step 3: Create a ticket

In the browser:

1. Enter a **Title**, e.g.: `Add rate limiting to the public API`
2. Enter a **Description** — paste the content from [docs/sample-ticket.md](sample-ticket.md) or write your own.
3. Click **Create ticket**.

The ticket is created and its details appear below the form.

---

## Step 4: Generate a planning brief

Click **Generate planning brief**.

- With the mock provider: the brief appears instantly.
- With DeepSeek: expect 10–30 seconds while the model responds.

The generated brief renders as markdown directly on the page.

---

## Step 5: Inspect via API (optional)

The full artifact is also accessible via the API:

```bash
# List artifacts for the ticket
curl http://localhost:8080/tickets/{ticket_id}/artifacts

# The ticket_id appears in the browser UI after creation
```

Interactive API docs are available at `http://localhost:8080/docs`.

---

## Step 6: Deploy to Cloud Run (optional)

Once GCP prerequisites are configured (see [README.md](../README.md) → Deployment):

1. Push or merge to `main`.
2. The `api-deploy.yml` workflow runs automatically:
   - Builds the Docker image
   - Pushes to Artifact Registry
   - Deploys to Cloud Run
3. The Cloud Run service URL is available in the GCP Console or via:
   ```bash
   gcloud run services describe incidentpilot-api --region us-central1 --format='value(status.url)'
   ```
