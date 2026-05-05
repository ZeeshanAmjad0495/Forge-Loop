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
