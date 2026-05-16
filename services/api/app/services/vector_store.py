"""Task 81: controlled project-memory vector retrieval.

Scope is deliberately narrow: semantic recall for *summarized* project
knowledge only — never broad RAG over the repo/code/logs/secrets.

The default provider is a dependency-free, deterministic in-memory store
(local term-frequency cosine — no embeddings API, no paid provider, no
external vector DB). This is the smallest local-first option and keeps
every test deterministic and offline. Chroma/Qdrant/pgvector are the
recommended *future* local adapters; selecting them today fails fast
(no import) — same designed-not-implemented pattern as Tasks 79/80.

Disabled by default (VECTOR_RETRIEVAL_ENABLED=false). ContextPack only
calls retrieval when explicitly enabled AND opted in per request.
Retrieval is project-scoped and bounded by count (top_k) and per-chunk
tokens. It is NEVER the source of truth.
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter

from pydantic import BaseModel, Field

from .. import config as _config
from .context_packs import estimate_tokens

# Only summarized, human-relevant knowledge may be indexed.
INDEXABLE_KINDS: tuple[str, ...] = (
    "project_memory_candidate",
    "project_memory",
    "artifact_summary",
    "architecture_decision",
    "human_feedback",
    "incident_lesson",
    "ci_lesson",
)
# Hard refusal: never index raw code/logs/secrets/binaries.
_REFUSED_KINDS: frozenset[str] = frozenset(
    {"raw_artifact", "secret", "log", "code", "repo", "binary", "raw_repo"}
)

_SUPPORTED = ("memory", "inmemory", "local", "")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class VectorDocument(BaseModel):
    document_id: str
    project_id: str
    kind: str
    source_type: str
    source_id: str
    text: str
    metadata: dict = Field(default_factory=dict)


class VectorMatch(BaseModel):
    document_id: str
    project_id: str
    kind: str
    source_type: str
    source_id: str
    score: float
    snippet: str


def _tokenize(text: str) -> Counter:
    return Counter(_TOKEN_RE.findall((text or "").lower()))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _bound_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0 or estimate_tokens(text) <= max_tokens:
        return text
    return text[: max_tokens * 4].rstrip() + "\n…[truncated]"


class VectorStore:
    backend: str = "abstract"

    def index(self, doc: VectorDocument) -> None:
        raise NotImplementedError

    def index_many(self, docs: list[VectorDocument]) -> int:
        raise NotImplementedError

    def query(
        self,
        project_id: str,
        text: str,
        *,
        top_k: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[VectorMatch]:
        raise NotImplementedError

    def delete_by_source(self, source_type: str, source_id: str) -> int:
        raise NotImplementedError

    def count(self, project_id: str | None = None) -> int:
        raise NotImplementedError

    def health_check(self) -> dict:
        raise NotImplementedError


def _validate_kind(kind: str) -> None:
    if kind in _REFUSED_KINDS:
        raise ValueError(
            f"Refusing to index kind={kind!r}: raw repo/code/logs/"
            "secrets/binaries are never indexed."
        )
    if kind == "raw_artifact" and not _config.VECTOR_INDEX_RAW_ARTIFACTS:
        raise ValueError("Raw artifacts are not indexable (policy).")
    if kind not in INDEXABLE_KINDS:
        raise ValueError(
            f"kind={kind!r} is not an indexable summary kind. "
            f"Allowed: {', '.join(INDEXABLE_KINDS)}"
        )


class MemoryVectorStore(VectorStore):
    """Deterministic, in-process, dependency-free. Default + tests."""

    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, VectorDocument] = {}
        self._vecs: dict[str, Counter] = {}

    def index(self, doc: VectorDocument) -> None:
        _validate_kind(doc.kind)
        bounded = _bound_tokens(doc.text, _config.VECTOR_MAX_CHUNK_TOKENS)
        stored = doc.model_copy(update={"text": bounded})
        with self._lock:
            self._docs[doc.document_id] = stored
            self._vecs[doc.document_id] = _tokenize(bounded)

    def index_many(self, docs: list[VectorDocument]) -> int:
        for d in docs:
            self.index(d)
        return len(docs)

    def query(
        self,
        project_id: str,
        text: str,
        *,
        top_k: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[VectorMatch]:
        k = top_k if top_k is not None else _config.VECTOR_TOP_K
        k = max(0, int(k))
        if k == 0:
            return []
        qv = _tokenize(text)
        kind_filter = set(kinds) if kinds else None
        with self._lock:
            scored: list[tuple[float, VectorDocument]] = []
            for doc_id, doc in self._docs.items():
                if doc.project_id != project_id:
                    continue
                if kind_filter and doc.kind not in kind_filter:
                    continue
                score = _cosine(qv, self._vecs[doc_id])
                if score <= 0.0:
                    continue
                scored.append((score, doc))
        # Deterministic ordering: score desc, then stable source/doc id.
        scored.sort(key=lambda s: (-s[0], s[1].source_id, s[1].document_id))
        out: list[VectorMatch] = []
        for score, doc in scored[:k]:
            out.append(
                VectorMatch(
                    document_id=doc.document_id,
                    project_id=doc.project_id,
                    kind=doc.kind,
                    source_type=doc.source_type,
                    source_id=doc.source_id,
                    score=round(score, 6),
                    snippet=_bound_tokens(
                        doc.text, _config.VECTOR_MAX_CHUNK_TOKENS
                    ),
                )
            )
        return out

    def delete_by_source(self, source_type: str, source_id: str) -> int:
        with self._lock:
            ids = [
                d_id
                for d_id, d in self._docs.items()
                if d.source_type == source_type and d.source_id == source_id
            ]
            for d_id in ids:
                self._docs.pop(d_id, None)
                self._vecs.pop(d_id, None)
            return len(ids)

    def count(self, project_id: str | None = None) -> int:
        with self._lock:
            if project_id is None:
                return len(self._docs)
            return sum(
                1 for d in self._docs.values() if d.project_id == project_id
            )

    def health_check(self) -> dict:
        return {
            "backend": self.backend,
            "healthy": True,
            "documents": self.count(),
        }


_singleton_lock = threading.Lock()
_instance: VectorStore | None = None


def _build() -> VectorStore:
    sel = (_config.VECTOR_PROVIDER or "memory").strip().lower()
    if sel in ("memory", "inmemory", "local", ""):
        return MemoryVectorStore()
    if sel in ("chroma", "qdrant", "pgvector"):
        raise RuntimeError(
            f"VECTOR_PROVIDER={sel} is a future local adapter and is not "
            "implemented yet (Task 81 ships the deterministic in-memory "
            "store only). Use VECTOR_PROVIDER=memory."
        )
    raise RuntimeError(
        f"Unsupported VECTOR_PROVIDER={sel!r}. Supported: memory "
        "(future: chroma, qdrant, pgvector)"
    )


def get_vector_store() -> VectorStore:
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = _build()
    return _instance


def reset_vector_store() -> None:
    """Drop the singleton (clears the index). Test/process hook."""
    global _instance
    with _singleton_lock:
        _instance = None


def retrieve_for_context(
    project_id: str,
    query_text: str,
    *,
    top_k: int | None = None,
    kinds: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Bounded retrieval for ContextPack. Returns (joined_text, source_ids).

    No-op (empty) unless VECTOR_RETRIEVAL_ENABLED. Bounded by top_k and
    per-chunk tokens. Citations are the matched source_ids.
    """
    if not _config.VECTOR_RETRIEVAL_ENABLED:
        return "", []
    matches = get_vector_store().query(
        project_id, query_text, top_k=top_k, kinds=kinds
    )
    if not matches:
        return "", []
    lines: list[str] = []
    source_ids: list[str] = []
    for m in matches:
        lines.append(f"[{m.kind}:{m.source_id}] {m.snippet}")
        if m.source_id not in source_ids:
            source_ids.append(m.source_id)
    return "\n\n".join(lines), source_ids


def vector_runtime_summary() -> dict:
    store = get_vector_store()
    try:
        health = store.health_check()
    except Exception as exc:  # noqa: BLE001
        health = {"healthy": False, "error": type(exc).__name__}
    return {
        "enabled": _config.VECTOR_RETRIEVAL_ENABLED,
        "configured_provider": (_config.VECTOR_PROVIDER or "memory"),
        "active_backend": store.backend,
        "top_k": _config.VECTOR_TOP_K,
        "max_chunk_tokens": _config.VECTOR_MAX_CHUNK_TOKENS,
        "index_artifact_summaries": _config.VECTOR_INDEX_ARTIFACT_SUMMARIES,
        "index_raw_artifacts": _config.VECTOR_INDEX_RAW_ARTIFACTS,
        "indexable_kinds": list(INDEXABLE_KINDS),
        "is_source_of_truth": False,
        "health": health,
    }


__all__ = [
    "VectorStore",
    "MemoryVectorStore",
    "VectorDocument",
    "VectorMatch",
    "INDEXABLE_KINDS",
    "get_vector_store",
    "reset_vector_store",
    "retrieve_for_context",
    "vector_runtime_summary",
]
