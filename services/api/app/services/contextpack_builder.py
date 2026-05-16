"""Task 78: layered ContextPack builder + token-budget reduction.

Reduces token usage by assembling *layered* context and shrinking it to a
budget BEFORE any costly model call, instead of dumping raw history.

Deterministic by design (tests must not depend on a provider): reduction
is structural (truncate then drop lowest-priority layers), and the
"compression provider" is only *recorded* (Ollama-preferred, DeepSeek
fallback, NEVER Kimi) — no LLM is invoked here. Reuses the existing
ContextPack record + prompt-context-cache foundations (no vector DB).
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from .. import config
from ..models import ContextPackPurpose
from . import prompt_context_cache as _cache
from .context_packs import create_context_pack, estimate_tokens

# Layers, highest retention priority first (last to be reduced/dropped).
_LAYER_ORDER: list[str] = [
    "project_profile",
    "quality_rules",
    "architecture_summary",
    "active_task_context",
    "relevant_requirements",
    "recent_human_feedback",
    "recent_decisions",
    "known_bugs_or_ci_failures",
    "relevant_artifacts",
]


class ContextPackBuildRequest(BaseModel):
    purpose: ContextPackPurpose = "custom"
    source_type: str = "manual"
    source_id: str = ""
    target_type: str | None = None
    target_id: str | None = None
    token_budget: int | None = None
    source_ids: list[str] = []
    # Caller-supplied candidate text per layer (request-driven, like the
    # other routing decisions). project_profile / architecture_summary /
    # quality_rules are auto-filled from project state when left blank.
    project_profile: str = ""
    architecture_summary: str = ""
    active_task_context: str = ""
    relevant_requirements: str = ""
    recent_human_feedback: str = ""
    recent_decisions: str = ""
    known_bugs_or_ci_failures: str = ""
    relevant_artifacts: str = ""
    quality_rules: str = ""


class ContextPackBuildResult(BaseModel):
    context_pack_id: str | None = None
    project_id: str
    purpose: ContextPackPurpose
    project_profile: str = ""
    architecture_summary: str = ""
    active_task_context: str = ""
    relevant_requirements: str = ""
    recent_human_feedback: str = ""
    recent_decisions: str = ""
    known_bugs_or_ci_failures: str = ""
    relevant_artifacts: str = ""
    quality_rules: str = ""
    excluded_context_reasoning: list[str] = []
    estimated_tokens: int = 0
    token_budget: int = 0
    compression_level: Literal["none", "light", "aggressive"] = "none"
    compression_provider: str = ""
    source_ids: list[str] = []
    warnings: list[str] = []
    cached: bool = False


def _resolve_compression_provider(warnings: list[str]) -> str:
    prov = config.CONTEXTPACK_COMPRESSION_PROVIDER
    if prov == "ollama" and not config.OLLAMA_ENABLED:
        prov = config.CONTEXTPACK_FALLBACK_PROVIDER
        warnings.append(
            "ollama_disabled_compression_fallback_to_"
            f"{config.CONTEXTPACK_FALLBACK_PROVIDER}"
        )
    if prov == config.EXPENSIVE_PROVIDER:  # never Kimi for compression
        warnings.append("kimi_not_allowed_for_compression_forced_deepseek")
        prov = "deepseek"
    return prov


def _autofill(req: ContextPackBuildRequest, project_id: str) -> dict[str, str]:
    from ..repositories_state import project_context_repo, project_repo

    layers = {name: getattr(req, name, "") or "" for name in _LAYER_ORDER}
    if not layers["project_profile"]:
        p = project_repo.get(project_id)
        if p is not None:
            layers["project_profile"] = (
                f"{p.name} | tech: {', '.join(p.tech_stack or [])} | "
                f"{(p.description or '')[:200]}"
            )
    ctx = project_context_repo.get(project_id)
    if ctx is not None:
        if not layers["architecture_summary"]:
            layers["architecture_summary"] = ctx.architecture_notes or ""
        if not layers["quality_rules"]:
            layers["quality_rules"] = "\n".join(
                s for s in (
                    ctx.coding_standards, ctx.safety_rules, ctx.domain_rules
                ) if s
            )
    return layers


def build_context_pack(
    *,
    project_id: str,
    body: ContextPackBuildRequest,
    persist: bool = True,
) -> ContextPackBuildResult:
    warnings: list[str] = []
    budget = min(
        int(body.token_budget or config.CONTEXTPACK_DEFAULT_TOKEN_BUDGET),
        int(config.CONTEXTPACK_MAX_TOKEN_BUDGET),
    )

    if not config.CONTEXTPACK_ENABLED:
        warnings.append("contextpack_disabled_passthrough")
        layers = _autofill(body, project_id)
        return ContextPackBuildResult(
            project_id=project_id, purpose=body.purpose,
            token_budget=budget, source_ids=list(body.source_ids),
            warnings=warnings,
            estimated_tokens=sum(
                estimate_tokens(v) for v in layers.values()
            ),
            **layers,
        )

    layers = _autofill(body, project_id)
    comp_provider = _resolve_compression_provider(warnings)

    # Cache lookup (project + source_ids + raw-content hash).
    from ..repositories_state import prompt_cache_repo

    basis = json.dumps(
        {
            "p": project_id,
            "s": sorted(body.source_ids),
            "b": budget,
            "L": layers,
        },
        sort_keys=True,
    )
    cache_key = None
    if config.CONTEXTPACK_CACHE_ENABLED:
        cache_key = _cache.compute_cache_key(
            project_id=project_id,
            cache_type="context_pack_render",
            source_type=body.source_type,
            source_id=body.source_id or None,
            content_hash_value=_cache.content_hash(basis),
        )
        hit = _cache.get_cached(prompt_cache_repo, cache_key)
        if hit is not None and hit.metadata.get("result"):
            _cache.record_hit(prompt_cache_repo, hit)
            cached = ContextPackBuildResult(**hit.metadata["result"])
            cached.cached = True
            return cached

    # Token accounting + structural reduction (deterministic).
    excluded: list[str] = []
    tokens = {n: estimate_tokens(layers[n]) for n in _LAYER_ORDER}
    total = sum(tokens.values())
    compression_level: Literal["none", "light", "aggressive"] = "none"

    if total > budget:
        # Pass 1: truncate lowest-priority layers (reverse order).
        for name in reversed(_LAYER_ORDER):
            if total <= budget:
                break
            if not layers[name]:
                continue
            over = total - budget
            # ~4 chars/token; trim this layer by what's needed (+marker).
            keep_tokens = max(0, tokens[name] - over)
            if keep_tokens < tokens[name]:
                keep_chars = max(0, keep_tokens * 4)
                if keep_chars == 0:
                    excluded.append(
                        f"dropped '{name}' (~{tokens[name]} tok) to fit "
                        f"{budget} token budget"
                    )
                    layers[name] = ""
                    compression_level = "aggressive"
                else:
                    layers[name] = (
                        layers[name][:keep_chars] + "\n…[truncated]"
                    )
                    excluded.append(
                        f"truncated '{name}' to ~{keep_tokens} tok"
                    )
                    if compression_level == "none":
                        compression_level = "light"
                tokens[name] = estimate_tokens(layers[name])
                total = sum(tokens.values())
        if total > budget:
            warnings.append(
                "context_exceeds_budget_after_reduction_"
                "context_reduction_recommended"
            )
            compression_level = "aggressive"

    final_tokens = sum(estimate_tokens(layers[n]) for n in _LAYER_ORDER)
    result = ContextPackBuildResult(
        project_id=project_id,
        purpose=body.purpose,
        excluded_context_reasoning=excluded,
        estimated_tokens=final_tokens,
        token_budget=budget,
        compression_level=compression_level,
        compression_provider=comp_provider,
        source_ids=list(body.source_ids),
        warnings=warnings,
        **layers,
    )

    if persist:
        content_summary = "\n\n".join(
            f"## {n}\n{layers[n]}" for n in _LAYER_ORDER if layers[n]
        )
        from ..repositories_state import context_pack_repo

        pack = create_context_pack(
            context_pack_repo,
            project_id=project_id,
            source_type=body.source_type,
            source_id=body.source_id or "context_pack_build",
            purpose=body.purpose,
            target_type=body.target_type,
            target_id=body.target_id,
            provider=comp_provider,
            content_summary=content_summary,
            rules_summary=layers["quality_rules"],
            estimated_tokens_value=final_tokens,
            compression_level=compression_level,
            excluded_context_reasoning=excluded,
            source_ids=list(body.source_ids),
            metadata={"layers": {n: layers[n] for n in _LAYER_ORDER}},
        )
        result.context_pack_id = pack.id

    if config.CONTEXTPACK_CACHE_ENABLED and cache_key is not None:
        try:
            _cache.set_cached(
                prompt_cache_repo,
                project_id=project_id,
                cache_type="context_pack_render",
                value=basis,
                summary=f"contextpack purpose={body.purpose}",
                source_type=body.source_type,
                source_id=body.source_id or None,
                estimated_tokens=final_tokens,
                metadata={"result": result.model_dump(mode="json")},
            )
        except Exception:
            pass

    return result


__all__ = [
    "ContextPackBuildRequest",
    "ContextPackBuildResult",
    "build_context_pack",
]
