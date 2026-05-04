import os

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "(default)")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
LLM_MODEL = os.getenv("LLM_MODEL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
REPOSITORY_PROVIDER = os.getenv("REPOSITORY_PROVIDER", "memory")
