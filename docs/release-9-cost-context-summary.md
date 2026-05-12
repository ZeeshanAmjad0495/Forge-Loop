# Release 9 — Cost & Context Optimization Summary

Release 9 adds the cost, context, routing, and budget foundation that lets
ForgeLoop reason about *how much* a workflow will cost and *which model* to
use, without yet implementing autonomous swarms or live billing integration.

All ten tasks (47–56) are implemented and covered by tests. Tests run with no
real provider, no real LLM, no GCP, and no network. The local-first /
cloud-optional architecture from Release 8 is preserved: every new repository
has memory, MongoDB (`local_document`), and Firestore implementations.

## Task list

| # | Task | Highlights |
|---|------|-----------|
| 47 | CostRecord + token tracking | `CostRecord` model, repo (memory/Mongo/Firestore), `services.cost_tracking.record_cost`, `GET/POST /projects/{id}/cost-records`. |
| 48 | ContextPack entity | `ContextPack` model + repo, `services.context_packs.create_context_pack`, `estimate_tokens` heuristic, `GET/POST /projects/{id}/context-packs`. |
| 49 | Typed memory retrieval policy | `services.memory_retrieval` with per-purpose default `DEFAULT_POLICIES`, approved-only filtering, tag/type filtering, `POST /projects/{id}/memory/retrieve`. No vector DB / RAG. |
| 50 | Artifact compression and summaries | `ArtifactSummary` model + repo, `services.artifact_summaries.summarize_artifact` deterministic fallback (short / agent-ready / structured), endpoints under `/artifacts/{id}/summaries`. |
| 51 | Model routing policy | `services.model_routing.decide_route` returns `ModelRouteDecision` for any workflow; routes `mock` for tests, `deepseek` for default reasoning, `kimi` for long-context / high-risk, `ollama` for local-support workflows (when enabled). `POST /projects/{id}/model-route/preview`, `GET /runtime/model-routing`. |
| 52 | Prompt / context cache | `PromptContextCacheEntry` model + repo, SHA-256 cache keys, `services.prompt_context_cache` (`set_cached`, `get_cached`, `record_hit`). Endpoints `/projects/{id}/prompt-context-cache`, `/prompt-context-cache/{id}` (GET/DELETE). |
| 53 | Budget controls | `BudgetPolicy` model + repo with per-period sum from `CostRecord`; `BudgetStatus` with `ok / warning / blocked / no_policy`. Endpoints for CRUD plus `/projects/{id}/budget-status` and `/projects/{id}/budget-check`. `ensure_budget_allows` helper for future enforcement points. |
| 54 | Ollama provider | New `app.llm.ollama.OllamaProvider` calls `/api/chat` via stdlib `urllib`. Disabled by default. Wired into routing for low-risk support workflows. Tests fully mocked. Defaults to `qwen2.5-coder:3b`. |
| 55 | Generic OpenAI-compatible provider | New `app.llm.openai_compatible.OpenAICompatibleProvider` reuses the existing `openai` SDK, supports any base URL, normalizes `usage` (prompt / completion / total / cached). Error messages sanitized — no key/body leakage. |
| 56 | Swarm budget control | `SwarmPolicy` model + repo, `services.swarm_budget.check_swarm_budget` enforces `max_agents`, `max_estimated_cost_usd`, allowed providers, and cross-checks the project budget. Blocks by default when no policy is defined. Endpoints under `/projects/{id}/swarm-policies` and `/projects/{id}/swarm-budget-check`. |

## Provider strategy (active)

| Provider | Role | Status |
|----------|------|--------|
| `mock` | Tests / smoke / demo | Always available. |
| `ollama` | Local low-risk support (summaries, compression, classification, memory extraction). M1 16GB target. | Disabled by default. Set `OLLAMA_ENABLED=true`. Recommended models: `qwen2.5-coder:1.5b`, `qwen2.5-coder:3b`, `qwen2.5-coder:7b`. |
| `deepseek` | Default serious reasoning, planning, coding, PR review. | Existing provider unchanged. |
| `kimi` | Long-context / complex agentic work, high-risk workflows. | Existing provider unchanged. |
| `openai_compatible` | Generic adapter for DeepSeek, Kimi, vLLM, SGLang, local gateways. | Disabled by default. Set `OPENAI_COMPATIBLE_ENABLED=true` + base URL + key. |

Routing picks providers automatically — callers no longer need to hard-code a
model per workflow. Existing explicit-provider overrides still work.

## What is out of scope (still parked)

- Live billing / provider pricing fetch.
- Real Ollama / DeepSeek / Kimi calls in tests.
- Embeddings, RAG, vector DB, semantic search.
- Real multi-agent swarm execution (LangGraph / multi-agent orchestration).
- Evaluator-style multi-candidate orchestration.
- ForgeLoop Studio modules (ProductScout, AuditLens, LaunchPilot).
- Redis / distributed cache.

## Tests

- Full backend suite: **919 passed, 1 skipped** (the Mongo *integration*
  test is skipped when no real Mongo server is reachable; the Mongo *parity*
  test runs in-memory via `mongomock` and passes).
- No real LLM, no real GCP, no real Mongo, no network calls.

## Known risks / follow-ups

- Cost records are only created when callers explicitly invoke
  `record_cost(...)`. Wiring this into the existing planning / requirement /
  PR-review flows is deliberately deferred — current providers don't surface
  token usage yet for DeepSeek/Kimi, and broad retrofit would inflate diff
  risk for Release 9.
- Budget enforcement is *advisory* until a caller invokes
  `ensure_budget_allows(...)`. Hooking that into the planning / PR-review
  routes is a Release 10 candidate.
- `OpenAICompatibleProvider` is registered but not yet aliased to replace
  the existing `DeepSeekProvider` / `KimiProvider` — Task 55 explicitly
  preserves current provider behavior.
- Swarm policies block by default when undefined. When swarms are
  introduced later, ensure operators create at least one policy first.
