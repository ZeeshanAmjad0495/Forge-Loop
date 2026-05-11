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
