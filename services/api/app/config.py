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
DEFAULT_REASONING_PROVIDER = os.getenv("DEFAULT_REASONING_PROVIDER", "deepseek")
LONG_CONTEXT_PROVIDER = os.getenv("LONG_CONTEXT_PROVIDER", "kimi")
LOCAL_SUPPORT_PROVIDER = os.getenv("LOCAL_SUPPORT_PROVIDER", "ollama")
TEST_PROVIDER = os.getenv("TEST_PROVIDER", "mock")
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
KODY_REVIEW_ENABLED = os.getenv("KODY_REVIEW_ENABLED", "false").lower() == "true"
KODY_BASE_URL = os.getenv("KODY_BASE_URL", "")
KODY_API_KEY = os.getenv("KODY_API_KEY", "")
FORGELOOP_WORKSPACE_ROOT = os.getenv("FORGELOOP_WORKSPACE_ROOT", "./.forgeloop/workspaces")
WORKSPACE_ALLOW_OUTSIDE_ROOT = os.getenv("WORKSPACE_ALLOW_OUTSIDE_ROOT", "false").lower() == "true"

_cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOWED_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

COMMAND_RUNNER_ENABLED = os.getenv("COMMAND_RUNNER_ENABLED", "false").lower() == "true"
COMMAND_RUNNER_MAX_TIMEOUT_SECONDS = int(os.getenv("COMMAND_RUNNER_MAX_TIMEOUT_SECONDS", "300"))
COMMAND_RUNNER_MAX_OUTPUT_BYTES = int(os.getenv("COMMAND_RUNNER_MAX_OUTPUT_BYTES", "200000"))

_DEFAULT_ALLOWED_COMMANDS = "python,python3,pytest,npm,node,npx,ruff,mypy"
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


def validate_startup_config() -> None:
    if AUTH_ENABLED and not AUTH_TOKEN_SECRET:
        raise RuntimeError(
            "AUTH_TOKEN_SECRET must be set when AUTH_ENABLED=true. "
            "Set a random secret of at least 32 characters."
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
