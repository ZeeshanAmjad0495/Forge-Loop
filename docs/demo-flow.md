# Demo Flow

Step-by-step guide to running ForgeLoop locally and generating a planning brief.

## Prerequisites

- Python 3.12+
- Node.js 18+
- (Optional) A DeepSeek API key, a Kimi (Moonshot) API key, or both — **or** use the mock provider (no key needed)

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

`LLM_PROVIDER` sets the **default** provider. The frontend lets you pick any configured provider per planning run, so you can leave the default as `mock` and still use DeepSeek or Kimi from the UI as long as their API keys are set.

To enable the **real DeepSeek provider**, add to `.env`:
```
DEEPSEEK_API_KEY=sk-your-deepseek-key
```

To enable the **real Kimi (Moonshot) provider**, add to `.env`:
```
KIMI_API_KEY=sk-your-kimi-key
```

To set DeepSeek (or Kimi) as the default instead of mock, also set `LLM_PROVIDER=deepseek` (or `kimi`).

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

## Step 4: Pick a provider and generate a planning brief

After the ticket is created, a **LLM provider** dropdown appears below the ticket details. It lists every implemented provider:

- `mock` — always available, instant response.
- `deepseek` — enabled if `DEEPSEEK_API_KEY` is set on the backend.
- `kimi` — enabled if `KIMI_API_KEY` is set on the backend.

Providers without an API key are shown as disabled. The default selection is whatever `LLM_PROVIDER` was set to on the backend.

Pick a provider and click **Generate planning brief**.

- With the mock provider: the brief appears instantly.
- With DeepSeek or Kimi: expect 10–30 seconds while the model responds.

The generated brief renders as markdown directly on the page. The response also includes the `agent_run.provider` and `agent_run.model` so it is auditable which provider produced the brief.

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
