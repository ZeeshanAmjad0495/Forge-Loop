"""Prompt / context cache (Release 9, Task 52).

Local repository-backed cache for stable summaries, prompt prefixes, and
context-pack renders. No Redis, no distributed cache, no provider prompt-cache
API integration.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from ..models import PromptContextCacheEntry, PromptContextCacheType
from ..repositories import PromptContextCacheRepository

CACHE_POLICY_VERSION = "v1"


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_cache_key(
    *,
    project_id: str,
    cache_type: str,
    source_type: str = "",
    source_id: str | None = None,
    content_hash_value: str = "",
    policy_version: str = CACHE_POLICY_VERSION,
) -> str:
    """Stable cache key independent of dict ordering."""
    parts = [
        f"project_id={project_id}",
        f"cache_type={cache_type}",
        f"source_type={source_type}",
        f"source_id={source_id or ''}",
        f"content_hash={content_hash_value}",
        f"policy_version={policy_version}",
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_cached(
    cache_repo: PromptContextCacheRepository,
    cache_key: str,
) -> PromptContextCacheEntry | None:
    entry = cache_repo.get_by_key(cache_key)
    if entry is None:
        return None
    if entry.expires_at is not None and entry.expires_at <= datetime.now(timezone.utc):
        return None
    return entry


def record_hit(
    cache_repo: PromptContextCacheRepository,
    entry: PromptContextCacheEntry,
) -> PromptContextCacheEntry:
    now = datetime.now(timezone.utc)
    entry.hit_count = entry.hit_count + 1
    entry.last_used_at = now
    entry.updated_at = now
    cache_repo.save(entry)
    return entry


def set_cached(
    cache_repo: PromptContextCacheRepository,
    *,
    project_id: str,
    cache_type: PromptContextCacheType,
    value: str,
    summary: str = "",
    source_type: str = "",
    source_id: str | None = None,
    estimated_tokens: int = 0,
    expires_at: datetime | None = None,
    metadata: dict | None = None,
) -> PromptContextCacheEntry:
    h = content_hash(value)
    key = compute_cache_key(
        project_id=project_id,
        cache_type=cache_type,
        source_type=source_type,
        source_id=source_id,
        content_hash_value=h,
    )
    existing = cache_repo.get_by_key(key)
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.value = value
        existing.summary = summary or existing.summary
        existing.estimated_tokens = estimated_tokens or existing.estimated_tokens
        existing.expires_at = expires_at
        existing.metadata = dict(metadata or existing.metadata or {})
        existing.updated_at = now
        cache_repo.save(existing)
        return existing

    entry = PromptContextCacheEntry(
        id=str(uuid.uuid4()),
        project_id=project_id,
        cache_key=key,
        cache_type=cache_type,
        source_type=source_type,
        source_id=source_id,
        content_hash=h,
        value=value,
        summary=summary,
        estimated_tokens=max(0, int(estimated_tokens)),
        hit_count=0,
        expires_at=expires_at,
        metadata=dict(metadata or {}),
        created_at=now,
        updated_at=now,
    )
    cache_repo.save(entry)
    return entry
