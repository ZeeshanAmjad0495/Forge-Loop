from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PromptContextCacheType = Literal[
    "project_context_summary",
    "project_memory_summary",
    "artifact_summary",
    "context_pack_render",
    "prompt_prefix",
    "model_route_decision",
    "custom",
]


class PromptContextCacheEntry(BaseModel):
    id: str
    project_id: str
    cache_key: str
    cache_type: PromptContextCacheType
    source_type: str = ""
    source_id: str | None = None
    content_hash: str
    value: str = ""
    summary: str = ""
    estimated_tokens: int = 0
    hit_count: int = 0
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
