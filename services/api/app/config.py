import os

# --- Release 8: Runtime profile ---
FORGELOOP_RUNTIME_PROFILE = os.getenv("FORGELOOP_RUNTIME_PROFILE", "local").strip().lower()

# --- Release 8 Task 43: Artifact storage ---
ARTIFACT_STORAGE_PROVIDER = os.getenv("ARTIFACT_STORAGE_PROVIDER", "database").strip().lower()
ARTIFACT_FILESYSTEM_ROOT = os.getenv("ARTIFACT_FILESYSTEM_ROOT", "./.forgeloop/artifacts")
ARTIFACT_MAX_INLINE_BYTES = int(os.getenv("ARTIFACT_MAX_INLINE_BYTES", "200000"))

# --- Release 8 Task 44: Secret provider ---
SECRET_PROVIDER = os.getenv("SECRET_PROVIDER", "env").strip().lower()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
LLM_MODEL = os.getenv("LLM_MODEL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1")
REPOSITORY_PROVIDER = os.getenv("REPOSITORY_PROVIDER", "memory")

# --- Release 9: Model routing ---
MODEL_ROUTING_ENABLED = os.getenv("MODEL_ROUTING_ENABLED", "true").lower() == "true"
# Release 10 / Task 87: every real LLM call must resolve its provider
# through the ModelRouter (services.model_routing.resolve_routed_provider).
# Default on. Set false only as an emergency escape hatch to restore the
# legacy "request override or LLM_PROVIDER" behavior.
MODEL_ROUTING_ENFORCED = (
    os.getenv("MODEL_ROUTING_ENFORCED", "true").lower() == "true"
)
# #46: Kimi is an EXPENSIVE provider, not a default routing target.
NORMAL_REASONING_PROVIDER = os.getenv(
    "NORMAL_REASONING_PROVIDER",
    os.getenv("DEFAULT_REASONING_PROVIDER", "deepseek"),
)
LOCAL_CHEAP_PROVIDER = os.getenv(
    "LOCAL_CHEAP_PROVIDER", os.getenv("LOCAL_SUPPORT_PROVIDER", "ollama")
)
EXPENSIVE_PROVIDER = os.getenv(
    "EXPENSIVE_PROVIDER", os.getenv("LONG_CONTEXT_PROVIDER", "kimi")
)
# Legacy aliases kept so existing imports/summary keep working.
DEFAULT_REASONING_PROVIDER = NORMAL_REASONING_PROVIDER
LONG_CONTEXT_PROVIDER = EXPENSIVE_PROVIDER
LOCAL_SUPPORT_PROVIDER = LOCAL_CHEAP_PROVIDER
TEST_PROVIDER = os.getenv("TEST_PROVIDER", "mock")
# Kimi/expensive routing controls — all default to the safe posture.
KIMI_AUTO_FALLBACK_ENABLED = (
    os.getenv("KIMI_AUTO_FALLBACK_ENABLED", "false").lower() == "true"
)
KIMI_REQUIRE_APPROVAL = (
    os.getenv("KIMI_REQUIRE_APPROVAL", "true").lower() == "true"
)
MODEL_ROUTING_PREFER_LOCAL = (
    os.getenv("MODEL_ROUTING_PREFER_LOCAL", "true").lower() == "true"
)
MODEL_ROUTING_CONTEXT_REDUCTION_FIRST = (
    os.getenv("MODEL_ROUTING_CONTEXT_REDUCTION_FIRST", "true").lower()
    == "true"
)

# Task 76: provider budget guards (cost control). All safe-by-default.
PROVIDER_BUDGETS_ENABLED = (
    os.getenv("PROVIDER_BUDGETS_ENABLED", "true").lower() == "true"
)
DAILY_KIMI_BUDGET_USD = float(os.getenv("DAILY_KIMI_BUDGET_USD", "0.50"))
DAILY_DEEPSEEK_BUDGET_USD = float(
    os.getenv("DAILY_DEEPSEEK_BUDGET_USD", "1.00")
)
MAX_KIMI_CALLS_PER_TASK = int(os.getenv("MAX_KIMI_CALLS_PER_TASK", "3"))
# Fail closed: if expensive-provider spend can't be computed, block it.
BUDGET_FAIL_CLOSED_FOR_EXPENSIVE = (
    os.getenv("BUDGET_FAIL_CLOSED_FOR_EXPENSIVE", "true").lower() == "true"
)
MODEL_ROUTING_LONG_CONTEXT_TOKENS = int(
    os.getenv("MODEL_ROUTING_LONG_CONTEXT_TOKENS", "32000")
)
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:3b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
OPENAI_COMPATIBLE_ENABLED = os.getenv("OPENAI_COMPATIBLE_ENABLED", "false").lower() == "true"
OPENAI_COMPATIBLE_BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "")
OPENAI_COMPATIBLE_API_KEY = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
OPENAI_COMPATIBLE_MODEL = os.getenv("OPENAI_COMPATIBLE_MODEL", "")
OPENAI_COMPATIBLE_PROVIDER_NAME = os.getenv(
    "OPENAI_COMPATIBLE_PROVIDER_NAME", "openai_compatible"
)
OPENAI_COMPATIBLE_TIMEOUT_SECONDS = int(os.getenv("OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "60"))
OPENAI_COMPATIBLE_MAX_CONTEXT_TOKENS = int(
    os.getenv("OPENAI_COMPATIBLE_MAX_CONTEXT_TOKENS", "32000")
)

# --- Task 40A: Local document database provider (MongoDB) ---
LOCAL_DOCUMENT_DB_PROVIDER = os.getenv("LOCAL_DOCUMENT_DB_PROVIDER", "mongodb")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "forgeloop_local")
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "3000"))
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "3000")
)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_ADMIN_EMAIL = os.getenv("AUTH_ADMIN_EMAIL", "")
AUTH_ADMIN_PASSWORD = os.getenv("AUTH_ADMIN_PASSWORD", "")
AUTH_TOKEN_SECRET = os.getenv("AUTH_TOKEN_SECRET", "")
# H1: disabling auth must be a deliberate, local-only opt-in — never a
# single silent env flip in a non-local environment.
FORGELOOP_ALLOW_NO_AUTH = (
    os.getenv("FORGELOOP_ALLOW_NO_AUTH", "false").lower() == "true"
)
# L1: minimum entropy for the JWT signing secret.
AUTH_TOKEN_SECRET_MIN_LEN = int(os.getenv("AUTH_TOKEN_SECRET_MIN_LEN", "32"))
# M4: bound every hosted-LLM call so a hung TLS connection cannot wedge
# a worker indefinitely.
LLM_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60")
)
# H8: cap LLM HTTP response reads (Ollama generations can be large but
# must still be bounded against a hostile/runaway endpoint).
LLM_MAX_RESPONSE_BYTES = int(
    os.getenv("LLM_MAX_RESPONSE_BYTES", "5000000")
)
# M5: operator escape hatch to allow http:// to a non-local LLM/bridge
# host (trusted internal network only). Default off = TLS enforced.
ALLOW_INSECURE_LLM_HTTP = (
    os.getenv("ALLOW_INSECURE_LLM_HTTP", "false").lower() == "true"
)
# H6: hard cap on request body size (JSON-bomb / memory-DoS defense).
# Generous — instruction packages / large diffs are well under this.
MAX_REQUEST_BODY_BYTES = int(
    os.getenv("MAX_REQUEST_BODY_BYTES", "10000000")
)
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))
OPENHANDS_EXECUTION_ENABLED = os.getenv("OPENHANDS_EXECUTION_ENABLED", "false").lower() == "true"
OPENHANDS_MODE = os.getenv("OPENHANDS_MODE", "dry_run")
OPENHANDS_COMMAND = os.getenv("OPENHANDS_COMMAND", "")
OPENHANDS_BASE_URL = os.getenv("OPENHANDS_BASE_URL", "")
OPENHANDS_TIMEOUT_SECONDS = int(os.getenv("OPENHANDS_TIMEOUT_SECONDS", "1800"))
OPENHANDS_MAX_OUTPUT_BYTES = int(os.getenv("OPENHANDS_MAX_OUTPUT_BYTES", "200000"))
OPENHANDS_EXECUTION_HARD_CAP_SECONDS = int(os.getenv("OPENHANDS_EXECUTION_HARD_CAP_SECONDS", "3600"))
_openhands_args_raw = os.getenv("OPENHANDS_ALLOWED_ARGS", "")
OPENHANDS_ALLOWED_ARGS: list[str] = [
    s.strip() for s in _openhands_args_raw.split(",") if s.strip()
]
OPENHANDS_EXECUTOR = os.getenv("OPENHANDS_EXECUTOR", "subprocess").lower()
OPENHANDS_HTTP_BASE_URL = os.getenv("OPENHANDS_HTTP_BASE_URL", "http://127.0.0.1:3000")
OPENHANDS_HTTP_POLL_INTERVAL_SECONDS = float(
    os.getenv("OPENHANDS_HTTP_POLL_INTERVAL_SECONDS", "2")
)
OPENHANDS_HTTP_QUIET_AFTER_SECONDS = float(
    os.getenv("OPENHANDS_HTTP_QUIET_AFTER_SECONDS", "10")
)
# B3: cap for the start-task -> READY (runtime spin-up) phase. Hard-coded
# 120s previously caused cold-runtime DTs to time out with zero output.
OPENHANDS_HTTP_RESOLVE_TIMEOUT_SECONDS = float(
    os.getenv("OPENHANDS_HTTP_RESOLVE_TIMEOUT_SECONDS", "300")
)
# H9: bound OpenHands bridge response reads (generous — event payloads can
# be large — but never unbounded against a hostile/runaway bridge).
OPENHANDS_HTTP_MAX_RESPONSE_BYTES = int(
    os.getenv("OPENHANDS_HTTP_MAX_RESPONSE_BYTES", "10000000")
)
OPENHANDS_HOST_PARENT_MOUNT = os.getenv("OPENHANDS_HOST_PARENT_MOUNT", "").strip()
OPENHANDS_CONTAINER_PARENT_MOUNT = os.getenv(
    "OPENHANDS_CONTAINER_PARENT_MOUNT", ""
).strip()
KODY_REVIEW_ENABLED = os.getenv("KODY_REVIEW_ENABLED", "false").lower() == "true"
KODY_BASE_URL = os.getenv("KODY_BASE_URL", "")
KODY_API_KEY = os.getenv("KODY_API_KEY", "")
KODY_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("KODY_REQUEST_TIMEOUT_SECONDS", "60")
)
KODY_MAX_RESPONSE_BYTES = int(
    os.getenv("KODY_MAX_RESPONSE_BYTES", "2000000")
)
# Kodus enqueues a job when x-kodus-async:1 is sent; ForgeLoop polls it.
KODY_ASYNC = os.getenv("KODY_ASYNC", "true").lower() == "true"

# C1: Aider coding runner. The runner is pure (instruction-package only,
# like OpenHands dry-run); external execution is independently gated and not
# implemented in this build. Aider reuses the configured LLM provider/key
# (e.g. DeepSeek) — no separate Aider API key.
AIDER_EXECUTION_ENABLED = (
    os.getenv("AIDER_EXECUTION_ENABLED", "false").lower() == "true"
)

# Task 77: RunnerRouter — pick the fastest safe runner, not OpenHands by
# default. Pure decision policy; execution stays gated by the *_ENABLED
# flags. Safe-by-default: OpenHands not auto-selected, requires approval.
RUNNER_ROUTING_ENABLED = (
    os.getenv("RUNNER_ROUTING_ENABLED", "true").lower() == "true"
)
# Task 90: make the RunnerRouter mandatory for real coding execution
# (OpenHands/Aider local). Default on. Set false only as an emergency
# escape hatch — the router decision is still recorded, just not enforced.
RUNNER_ROUTER_ENFORCED = (
    os.getenv("RUNNER_ROUTER_ENFORCED", "true").lower() == "true"
)
DEFAULT_CODING_RUNNER = os.getenv("DEFAULT_CODING_RUNNER", "lightweight")
OPENHANDS_AUTO_SELECT_ENABLED = (
    os.getenv("OPENHANDS_AUTO_SELECT_ENABLED", "false").lower() == "true"
)
OPENHANDS_REQUIRE_APPROVAL = (
    os.getenv("OPENHANDS_REQUIRE_APPROVAL", "true").lower() == "true"
)
# Minimum task complexity at which OpenHands becomes eligible.
OPENHANDS_MIN_COMPLEXITY = os.getenv("OPENHANDS_MIN_COMPLEXITY", "medium")
LIGHTWEIGHT_RUNNER_ENABLED = (
    os.getenv("LIGHTWEIGHT_RUNNER_ENABLED", "true").lower() == "true"
)
RUNNER_MAX_PARALLEL_LOCAL = int(
    os.getenv("RUNNER_MAX_PARALLEL_LOCAL", "1")
)

# Task 78: layered ContextPack + token-budget reduction (cost control).
# Compression prefers local Ollama, falls back to DeepSeek — never Kimi.
CONTEXTPACK_ENABLED = (
    os.getenv("CONTEXTPACK_ENABLED", "true").lower() == "true"
)
# Task 89: require a ContextPack for every real model-facing routed call
# (built+linked at the resolve_routed_provider chokepoint). Default on.
CONTEXTPACK_ENFORCED = (
    os.getenv("CONTEXTPACK_ENFORCED", "true").lower() == "true"
)
# Task 89: when raw assembled context cannot fit the token budget,
# warn by default; set true to hard-block (4xx) instead.
CONTEXTPACK_BLOCK_OVERSIZED = (
    os.getenv("CONTEXTPACK_BLOCK_OVERSIZED", "false").lower() == "true"
)
CONTEXTPACK_DEFAULT_TOKEN_BUDGET = int(
    os.getenv("CONTEXTPACK_DEFAULT_TOKEN_BUDGET", "12000")
)
CONTEXTPACK_MAX_TOKEN_BUDGET = int(
    os.getenv("CONTEXTPACK_MAX_TOKEN_BUDGET", "24000")
)
CONTEXTPACK_COMPRESSION_PROVIDER = os.getenv(
    "CONTEXTPACK_COMPRESSION_PROVIDER", "ollama"
)
CONTEXTPACK_FALLBACK_PROVIDER = os.getenv(
    "CONTEXTPACK_FALLBACK_PROVIDER", "deepseek"
)
CONTEXTPACK_CACHE_ENABLED = (
    os.getenv("CONTEXTPACK_CACHE_ENABLED", "true").lower() == "true"
)
# Project decision: Aider uses the local Ollama by default (keeps codegen
# off hosted providers). Override with AIDER_LLM_PROVIDER if needed.
AIDER_LLM_PROVIDER = os.getenv("AIDER_LLM_PROVIDER", "ollama")
AIDER_MODEL = os.getenv("AIDER_MODEL", "")  # blank -> provider default
# Aider execution bridge (real subprocess). Server-controlled argv only;
# request input can never influence the command line.
AIDER_COMMAND = os.getenv("AIDER_COMMAND", "aider")
AIDER_TIMEOUT_SECONDS = int(os.getenv("AIDER_TIMEOUT_SECONDS", "900"))
AIDER_MAX_OUTPUT_BYTES = int(os.getenv("AIDER_MAX_OUTPUT_BYTES", "200000"))
AIDER_EXECUTION_HARD_CAP_SECONDS = int(
    os.getenv("AIDER_EXECUTION_HARD_CAP_SECONDS", "3600")
)

# C2: Langfuse observability. Non-secret bits live here; the secret key is
# resolved via the secret provider at runtime (never committed). Provider is
# a no-op unless host + both keys are present.
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
FORGELOOP_WORKSPACE_ROOT = os.getenv("FORGELOOP_WORKSPACE_ROOT", "./.forgeloop/workspaces")
WORKSPACE_ALLOW_OUTSIDE_ROOT = os.getenv("WORKSPACE_ALLOW_OUTSIDE_ROOT", "false").lower() == "true"

_cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOWED_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

COMMAND_RUNNER_ENABLED = os.getenv("COMMAND_RUNNER_ENABLED", "false").lower() == "true"
COMMAND_RUNNER_MAX_TIMEOUT_SECONDS = int(os.getenv("COMMAND_RUNNER_MAX_TIMEOUT_SECONDS", "300"))
COMMAND_RUNNER_MAX_OUTPUT_BYTES = int(os.getenv("COMMAND_RUNNER_MAX_OUTPUT_BYTES", "200000"))

# #45/H3: interpreter escapes (bash/python/node/npx/npm) are NO LONGER on
# the default allowlist — allowlisting an interpreter is equivalent to
# allowing arbitrary execution (it nullifies the argv[0] blocklist via
# `bash -c` / `python -c`). The default set is the concrete QA tooling
# only. Operators that genuinely need an interpreter must add it
# explicitly via COMMAND_RUNNER_ALLOWED_COMMANDS (informed opt-in).
_DEFAULT_ALLOWED_COMMANDS = "pytest,ruff,mypy,uv"
# #45/H3: opt-in shell-mode check definitions (CheckDefinition.shell=True
# -> `bash -lc "<raw>"`) bypass token validation entirely, so they are
# now gated behind an explicit flag (default off). Without it a
# shell-mode check is blocked rather than silently granting full RCE.
COMMAND_RUNNER_ALLOW_SHELL = (
    os.getenv("COMMAND_RUNNER_ALLOW_SHELL", "false").lower() == "true"
)
_DEFAULT_BLOCKED_COMMANDS = (
    "sudo,su,rm,rmdir,chmod,chown,curl,wget,ssh,scp,rsync,"
    "git,gh,docker,docker-compose,terraform,kubectl,gcloud,"
    "aws,az,openhands,aider,cline,opencode"
)
_allowed_raw = os.getenv("COMMAND_RUNNER_ALLOWED_COMMANDS", _DEFAULT_ALLOWED_COMMANDS)
_blocked_raw = os.getenv("COMMAND_RUNNER_BLOCKED_COMMANDS", _DEFAULT_BLOCKED_COMMANDS)
COMMAND_RUNNER_ALLOWED_COMMANDS: list[str] = [
    s.strip() for s in _allowed_raw.split(",") if s.strip()
]
COMMAND_RUNNER_BLOCKED_COMMANDS: list[str] = [
    s.strip() for s in _blocked_raw.split(",") if s.strip()
]

# --- Task 37: Local Git Branch Workflow ---
GIT_WORKFLOW_ENABLED = os.getenv("GIT_WORKFLOW_ENABLED", "false").lower() == "true"
GIT_COMMIT_ENABLED = os.getenv("GIT_COMMIT_ENABLED", "false").lower() == "true"
GIT_ALLOWED_BRANCH_PREFIX = os.getenv("GIT_ALLOWED_BRANCH_PREFIX", "forgeloop/")
_git_protected_raw = os.getenv(
    "GIT_PROTECTED_BRANCHES", "main,master,develop,production,release"
)
GIT_PROTECTED_BRANCHES: list[str] = [
    s.strip() for s in _git_protected_raw.split(",") if s.strip()
]
# B2 stale-base hardening: when true, an integration run whose base is
# behind its local upstream (origin/<base>) is refused (409 STALE_BASE)
# instead of silently producing a branch that conflicts with current
# base. Default false: always DETECT + warn, block only when opted in.
INTEGRATION_REQUIRE_CURRENT_BASE = (
    os.getenv("INTEGRATION_REQUIRE_CURRENT_BASE", "false").lower() == "true"
)
GIT_TIMEOUT_SECONDS = int(os.getenv("GIT_TIMEOUT_SECONDS", "60"))
GIT_MAX_DIFF_BYTES = int(os.getenv("GIT_MAX_DIFF_BYTES", "200000"))
GIT_COMMIT_MESSAGE_MAX_LEN = int(os.getenv("GIT_COMMIT_MESSAGE_MAX_LEN", "2000"))
GIT_BINARY = os.getenv("GIT_BINARY", "git")

# --- Task 38: GitHub draft PR creation ---
GITHUB_INTEGRATION_ENABLED = os.getenv("GITHUB_INTEGRATION_ENABLED", "false").lower() == "true"
GITHUB_PUSH_ENABLED = os.getenv("GITHUB_PUSH_ENABLED", "false").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
GITHUB_DEFAULT_REMOTE = os.getenv("GITHUB_DEFAULT_REMOTE", "origin")
GITHUB_PR_DRAFT_DEFAULT = os.getenv("GITHUB_PR_DRAFT_DEFAULT", "true").lower() == "true"
GITHUB_REQUEST_TIMEOUT_SECONDS = int(os.getenv("GITHUB_REQUEST_TIMEOUT_SECONDS", "30"))
GITHUB_MAX_RESPONSE_BYTES = int(os.getenv("GITHUB_MAX_RESPONSE_BYTES", "200000"))

# --- Task 79: local-first cache / ephemeral-state (Valkey/Redis) ---
# Accelerator only — NEVER the source of truth (durable records stay in
# the repository provider). Default backend is in-memory: no dependency,
# deterministic, used by every test. `redis`/`valkey` is loaded lazily
# and only when selected.
CACHE_PROVIDER = os.getenv("CACHE_PROVIDER", "memory").strip().lower()
CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
CACHE_DEFAULT_TTL_SECONDS = int(os.getenv("CACHE_DEFAULT_TTL_SECONDS", "3600"))
CACHE_CONNECT_TIMEOUT_MS = int(os.getenv("CACHE_CONNECT_TIMEOUT_MS", "1000"))
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
# Non-critical cache may fall back to in-memory if Redis is unreachable.
CACHE_FAIL_OPEN = os.getenv("CACHE_FAIL_OPEN", "true").lower() == "true"
# The expensive-provider budget/rate-limit guard must NOT silently trust
# a degraded cache (the durable CostRecord guard remains authoritative).
RATE_LIMIT_CACHE_FAIL_OPEN = (
    os.getenv("RATE_LIMIT_CACHE_FAIL_OPEN", "false").lower() == "true"
)

# --- Task 80 (Phase A): durable workflow + event foundation ---
# Local-first. Defaults are in-memory: no dependency, deterministic,
# used by every test. NATS (EventBus) and Temporal (WorkflowEngine) are
# designed-for but Phase B — selecting them fails fast (no import). K3s
# is an optional spike, documented only (never a default runtime).
EVENT_BUS_PROVIDER = os.getenv("EVENT_BUS_PROVIDER", "memory").strip().lower()
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
WORKFLOW_ENGINE_PROVIDER = os.getenv(
    "WORKFLOW_ENGINE_PROVIDER", "memory"
).strip().lower()
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
# Task 93: best-effort WorkflowEngine tracking for the one migrated
# workflow (incident_to_triage). Default on; the engine is deterministic
# + side-effect-free and never the source of truth, so tracking never
# changes durable behavior. Failures are swallowed.
WORKFLOW_ENGINE_TRACKING_ENABLED = (
    os.getenv("WORKFLOW_ENGINE_TRACKING_ENABLED", "true").lower() == "true"
)
WORKER_ENABLED = os.getenv("WORKER_ENABLED", "false").lower() == "true"
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "1"))

# --- Task 81: controlled project-memory vector retrieval ---
# Narrow, local-first, OFF by default. Indexes summarized knowledge only
# (memory, artifact summaries, decisions, feedback, incident/CI lessons)
# — never raw repo/code/logs/secrets. Default provider is a dependency-
# free deterministic in-memory store; chroma/qdrant/pgvector are future
# local adapters (selecting them fails fast, no import). Bounded by
# top_k + per-chunk tokens. Never the source of truth.
VECTOR_RETRIEVAL_ENABLED = (
    os.getenv("VECTOR_RETRIEVAL_ENABLED", "false").lower() == "true"
)
VECTOR_PROVIDER = os.getenv("VECTOR_PROVIDER", "memory").strip().lower()
VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "5"))
VECTOR_MAX_CHUNK_TOKENS = int(os.getenv("VECTOR_MAX_CHUNK_TOKENS", "800"))
VECTOR_INDEX_ARTIFACT_SUMMARIES = (
    os.getenv("VECTOR_INDEX_ARTIFACT_SUMMARIES", "true").lower() == "true"
)
VECTOR_INDEX_RAW_ARTIFACTS = (
    os.getenv("VECTOR_INDEX_RAW_ARTIFACTS", "false").lower() == "true"
)

# --- Task 82: free/local-first observability ---
# In-process Prometheus-text /metrics + structured JSON event logs. No
# client library, no OpenTelemetry import (OTEL is a config flag only —
# heavy dependency, deferred), no paid monitoring. All instrumentation
# is a no-op unless OBSERVABILITY_ENABLED and METRICS_ENABLED.
OBSERVABILITY_ENABLED = (
    os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true"
)
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
METRICS_PATH = os.getenv("METRICS_PATH", "/metrics")
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
STRUCTURED_LOGS_ENABLED = (
    os.getenv("STRUCTURED_LOGS_ENABLED", "true").lower() == "true"
)

# --- Task 83: advisory-only auto-remediation ---
# OFF by default. Even when enabled it is ADVISORY ONLY: CI/incident/PR-
# review findings can become a RemediationProposal draft, but a human
# Approval is required before a DevTask is created. ForgeLoop never
# auto-merges, auto-deploys, or creates branches/PRs from remediation.
AUTO_REMEDIATION_ENABLED = (
    os.getenv("AUTO_REMEDIATION_ENABLED", "false").lower() == "true"
)
AUTO_REMEDIATION_ADVISORY_ONLY = (
    os.getenv("AUTO_REMEDIATION_ADVISORY_ONLY", "true").lower() == "true"
)
AUTO_REMEDIATION_CREATE_TASKS_REQUIRE_APPROVAL = (
    os.getenv(
        "AUTO_REMEDIATION_CREATE_TASKS_REQUIRE_APPROVAL", "true"
    ).lower()
    == "true"
)
AUTO_REMEDIATION_ALLOW_BRANCH_CREATION = (
    os.getenv("AUTO_REMEDIATION_ALLOW_BRANCH_CREATION", "false").lower()
    == "true"
)
AUTO_REMEDIATION_ALLOW_PR_CREATION = (
    os.getenv("AUTO_REMEDIATION_ALLOW_PR_CREATION", "false").lower()
    == "true"
)


def validate_startup_config() -> None:
    if AUTH_ENABLED and not AUTH_TOKEN_SECRET:
        raise RuntimeError(
            "AUTH_TOKEN_SECRET must be set when AUTH_ENABLED=true. "
            "Set a random secret of at least 32 characters."
        )
    # L1: enforce signing-secret entropy (was only checked non-empty).
    if AUTH_ENABLED and len(AUTH_TOKEN_SECRET) < AUTH_TOKEN_SECRET_MIN_LEN:
        raise RuntimeError(
            f"AUTH_TOKEN_SECRET must be >= {AUTH_TOKEN_SECRET_MIN_LEN} "
            "characters (weak secrets enable offline JWT forgery)."
        )
    # H1: refuse to run anonymously unless it is an explicit, local-only
    # opt-in. A single AUTH_ENABLED=false flip must not silently expose
    # the entire control plane (incl. execution endpoints).
    if not AUTH_ENABLED:
        if ENVIRONMENT != "local" or not FORGELOOP_ALLOW_NO_AUTH:
            raise RuntimeError(
                "AUTH_ENABLED=false is refused: it makes every endpoint "
                "(including code execution) anonymous. To run without auth "
                "you must set ENVIRONMENT=local AND "
                "FORGELOOP_ALLOW_NO_AUTH=true (local development only)."
            )
    if REPOSITORY_PROVIDER == "local_document":
        if LOCAL_DOCUMENT_DB_PROVIDER != "mongodb":
            raise RuntimeError(
                "Unsupported LOCAL_DOCUMENT_DB_PROVIDER="
                f"{LOCAL_DOCUMENT_DB_PROVIDER!r}. Supported: mongodb"
            )
        if not MONGODB_URI:
            raise RuntimeError(
                "MONGODB_URI must be set when REPOSITORY_PROVIDER=local_document."
            )
    if CACHE_PROVIDER not in (
        "memory", "inmemory", "local", "redis", "valkey", ""
    ):
        raise RuntimeError(
            f"Unsupported CACHE_PROVIDER={CACHE_PROVIDER!r}. "
            "Supported: memory, redis, valkey"
        )
    if EVENT_BUS_PROVIDER not in (
        "memory", "inmemory", "local", "nats", ""
    ):
        raise RuntimeError(
            f"Unsupported EVENT_BUS_PROVIDER={EVENT_BUS_PROVIDER!r}. "
            "Supported: memory, nats"
        )
    if WORKFLOW_ENGINE_PROVIDER not in (
        "memory", "inmemory", "local", "temporal", ""
    ):
        raise RuntimeError(
            "Unsupported WORKFLOW_ENGINE_PROVIDER="
            f"{WORKFLOW_ENGINE_PROVIDER!r}. Supported: memory, temporal"
        )
    if VECTOR_PROVIDER not in (
        "memory", "inmemory", "local", "chroma", "qdrant", "pgvector", ""
    ):
        raise RuntimeError(
            f"Unsupported VECTOR_PROVIDER={VECTOR_PROVIDER!r}. "
            "Supported: memory (future: chroma, qdrant, pgvector)"
        )
    # Safety: advisory-only must never permit branch/PR automation.
    if AUTO_REMEDIATION_ADVISORY_ONLY and (
        AUTO_REMEDIATION_ALLOW_BRANCH_CREATION
        or AUTO_REMEDIATION_ALLOW_PR_CREATION
    ):
        raise RuntimeError(
            "AUTO_REMEDIATION_ADVISORY_ONLY=true forbids "
            "AUTO_REMEDIATION_ALLOW_BRANCH_CREATION / "
            "AUTO_REMEDIATION_ALLOW_PR_CREATION. Auto-remediation must "
            "not create branches or PRs."
        )


# --- Task 92: DB-backed local background worker ---
# Off by default. The worker only drains jobs when explicitly invoked
# (POST /jobs/worker/run-once); there is no daemon thread. The Job
# repository is the durable source of truth.
BACKGROUND_WORKER_ENABLED = (
    os.getenv("BACKGROUND_WORKER_ENABLED", "false").lower() == "true"
)
JOB_DEFAULT_MAX_ATTEMPTS = int(os.getenv("JOB_DEFAULT_MAX_ATTEMPTS", "3"))
JOB_DEFAULT_TIMEOUT_SECONDS = int(
    os.getenv("JOB_DEFAULT_TIMEOUT_SECONDS", "300")
)
JOB_WORKER_MAX_DRAIN = int(os.getenv("JOB_WORKER_MAX_DRAIN", "10"))
