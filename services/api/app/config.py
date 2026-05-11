import os

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
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_ADMIN_EMAIL = os.getenv("AUTH_ADMIN_EMAIL", "")
AUTH_ADMIN_PASSWORD = os.getenv("AUTH_ADMIN_PASSWORD", "")
AUTH_TOKEN_SECRET = os.getenv("AUTH_TOKEN_SECRET", "")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))
OPENHANDS_EXECUTION_ENABLED = os.getenv("OPENHANDS_EXECUTION_ENABLED", "false").lower() == "true"
OPENHANDS_MODE = os.getenv("OPENHANDS_MODE", "dry_run")
OPENHANDS_COMMAND = os.getenv("OPENHANDS_COMMAND", "")
OPENHANDS_BASE_URL = os.getenv("OPENHANDS_BASE_URL", "")
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


def validate_startup_config() -> None:
    if AUTH_ENABLED and not AUTH_TOKEN_SECRET:
        raise RuntimeError(
            "AUTH_TOKEN_SECRET must be set when AUTH_ENABLED=true. "
            "Set a random secret of at least 32 characters."
        )
