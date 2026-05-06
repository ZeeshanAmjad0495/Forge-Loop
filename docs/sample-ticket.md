# Sample Ticket

Use this as a realistic input to the planning agent when demoing or testing ForgeLoop.

---

## Title

Add rate limiting to the public API

## Description

We are seeing occasional request spikes from a small number of clients that cause latency increases for everyone else. Add per-IP rate limiting to the public API to protect downstream services.

Requirements:
- Return HTTP 429 Too Many Requests when a client exceeds the configured threshold.
- Include a `Retry-After` header in 429 responses.
- Rate limit window and maximum requests per window should be configurable via environment variables (e.g. `RATE_LIMIT_WINDOW_SECONDS=60`, `RATE_LIMIT_MAX_REQUESTS=100`).
- Provide sensible defaults so the service works without the variables set.

## Acceptance criteria

- [ ] Requests from a single IP within the configured limit are processed normally.
- [ ] Requests that exceed the limit receive HTTP 429 with a `Retry-After` header.
- [ ] `RATE_LIMIT_WINDOW_SECONDS` and `RATE_LIMIT_MAX_REQUESTS` env vars control the limit.
- [ ] When env vars are absent, the service applies the default limits without error.
- [ ] Unit tests cover: below-limit, at-limit, and above-limit scenarios.
- [ ] Existing endpoint tests continue to pass with rate limiting enabled.

## Edge cases

- **Reverse proxy / Cloud Run**: Real client IP must be extracted from `X-Forwarded-For`; using `request.client.host` alone will rate-limit the proxy, not the client.
- **Distributed instances**: Cloud Run can run multiple instances concurrently. An in-process counter is not shared across instances. The brief should address whether in-process limiting is acceptable for MVP or whether a shared store (e.g. Redis, Memorystore) is required.
- **Burst traffic**: Clarify whether a fixed window (simple) or sliding window (smoother) is required. The approach affects both implementation complexity and perceived fairness.
- **Internal / health-check traffic**: Ensure `/health` probes from Cloud Run are not counted against client limits.

## Expected planning output

The planning agent should produce an implementation brief covering:

1. **Requirement summary** — what is being rate-limited and why
2. **Technical approach** — chosen middleware/library, window strategy, IP extraction
3. **Environment variable schema** — variable names, types, defaults
4. **Task breakdown** — ordered implementation steps
5. **Test strategy** — unit tests for limit logic; integration test with TestClient
6. **Edge cases** — reverse proxy IP, multi-instance state, health probes
7. **Risks** — shared state across Cloud Run instances; choosing in-process vs. external store
8. **Human approval points** — before merging to production, confirm chosen rate-limiting strategy with the team
