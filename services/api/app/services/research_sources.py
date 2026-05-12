"""Research source cache service (Release 11, Task 64).

Structured store for source records that research briefs and architecture
decisions can cite. Does NOT fetch URLs, scrape the web, or make any network
calls — sources are created from explicit caller-provided metadata only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models import (
    ResearchBrief,
    ResearchSource,
    ResearchSourceCreate,
    ResearchSourceUpdate,
)
from ..repositories import (
    ResearchBriefRepository,
    ResearchSourceRepository,
)


def create_source(
    repo: ResearchSourceRepository,
    *,
    body: ResearchSourceCreate,
) -> ResearchSource:
    now = datetime.now(timezone.utc)
    source = ResearchSource(
        id=str(uuid.uuid4()),
        project_id=body.project_id,
        title=body.title,
        source_type=body.source_type,
        url=body.url,
        author=body.author,
        published_at=body.published_at,
        accessed_at=body.accessed_at or now,
        summary=body.summary,
        key_points=list(body.key_points),
        relevance=body.relevance,
        trust_level=body.trust_level,
        tags=list(body.tags),
        cache_key=body.cache_key,
        created_at=now,
        updated_at=now,
    )
    repo.save(source)
    return source


def update_source(
    repo: ResearchSourceRepository,
    source: ResearchSource,
    body: ResearchSourceUpdate,
) -> ResearchSource:
    data = source.model_dump()
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        data[field] = value
    data["updated_at"] = datetime.now(timezone.utc)
    updated = ResearchSource(**data)
    repo.update(updated)
    return updated


def attach_source_to_brief(
    brief_repo: ResearchBriefRepository,
    brief: ResearchBrief,
    source_id: str,
) -> ResearchBrief:
    if source_id in brief.source_ids:
        return brief
    new_ids = list(brief.source_ids) + [source_id]
    updated = brief.model_copy(
        update={
            "source_ids": new_ids,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    brief_repo.update(updated)
    return updated
