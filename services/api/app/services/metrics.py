"""Task 82: free/local-first observability.

A dependency-free, in-process metrics registry exposed in Prometheus
text format at `/metrics`. No client library, no OpenTelemetry import
(OTEL is config-flagged but Phase-deferred — heavy dependency), no paid
monitoring, no Cloud Logging polling, no alert routing.

Everything is a no-op unless OBSERVABILITY_ENABLED and METRICS_ENABLED,
so instrumentation at chokepoints never changes behavior or tests.
Metrics are aggregate counters/summaries only — never secrets, tokens,
prompts, or PII. Not a source of truth.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Literal

from .. import config as _config

_MetricType = Literal["counter", "summary"]

# name -> (type, help). Declared so /metrics emits HELP/TYPE.
_KNOWN: dict[str, tuple[_MetricType, str]] = {
    "llm_route_decision_total": ("counter", "Model-route decisions"),
    "provider_call_total": ("counter", "Completed provider calls"),
    "provider_call_failed_total": ("counter", "Failed provider calls"),
    "provider_estimated_cost_usd_total": (
        "counter",
        "Estimated provider cost (USD)",
    ),
    "kimi_blocked_total": (
        "counter",
        "Expensive-provider calls blocked by the budget guard",
    ),
    "runner_selected_total": ("counter", "Runner selections"),
    "runner_duration_seconds": ("summary", "Runner execution duration"),
    "contextpack_tokens_before_total": (
        "counter",
        "ContextPack tokens before reduction",
    ),
    "contextpack_tokens_after_total": (
        "counter",
        "ContextPack tokens after reduction",
    ),
    "workflow_started_total": ("counter", "Workflows started"),
    "workflow_failed_total": ("counter", "Workflows failed"),
    "approval_wait_seconds": ("summary", "Human-approval wait duration"),
    # Task 96 — Release 10 chokepoint signals.
    "provider_rate_limited_total": (
        "counter",
        "Provider calls blocked by the Task-95 rate limit",
    ),
    "cache_hit_total": ("counter", "Ephemeral cache hits"),
    "cache_miss_total": ("counter", "Ephemeral cache misses"),
    "remediation_proposal_total": (
        "counter",
        "Advisory remediation proposals created",
    ),
}

_lock = threading.RLock()
_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
# (name, labels) -> [count, sum]
_summaries: dict[
    tuple[str, tuple[tuple[str, str], ...]], list[float]
] = {}

_events_logger = logging.getLogger("forgeloop.events")


def _enabled() -> bool:
    return _config.OBSERVABILITY_ENABLED and _config.METRICS_ENABLED


def _key(labels: dict | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    clean: list[tuple[str, str]] = []
    for k, v in labels.items():
        sv = str(v).replace("\\", "_").replace('"', "_").replace("\n", " ")
        clean.append((str(k), sv[:120]))
    return tuple(sorted(clean))


def inc(name: str, value: float = 1.0, **labels) -> None:
    if not _enabled():
        return
    with _lock:
        k = (name, _key(labels))
        _counters[k] = _counters.get(k, 0.0) + float(value)


def observe(name: str, value: float, **labels) -> None:
    if not _enabled():
        return
    with _lock:
        k = (name, _key(labels))
        agg = _summaries.setdefault(k, [0.0, 0.0])
        agg[0] += 1.0
        agg[1] += float(value)


def log_event(event: str, **fields) -> None:
    """Structured JSON log line. No-op unless STRUCTURED_LOGS_ENABLED."""
    if not _config.STRUCTURED_LOGS_ENABLED:
        return
    try:
        _events_logger.info(json.dumps({"event": event, **fields}))
    except Exception:
        pass


def reset() -> None:
    """Test/process hook."""
    with _lock:
        _counters.clear()
        _summaries.clear()


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_esc(v)}"' for k, v in labels)
    return "{" + inner + "}"


def render() -> str:
    """Prometheus text exposition (deterministic ordering)."""
    lines: list[str] = []
    with _lock:
        counters = dict(_counters)
        summaries = {k: list(v) for k, v in _summaries.items()}
    emitted_help: set[str] = set()

    def _header(name: str) -> None:
        if name in emitted_help:
            return
        emitted_help.add(name)
        mtype, helptext = _KNOWN.get(name, ("counter", name))
        lines.append(f"# HELP {name} {helptext}")
        lines.append(f"# TYPE {name} {mtype}")

    for (name, labels) in sorted(counters):
        _header(name)
        lines.append(f"{name}{_fmt_labels(labels)} {counters[(name, labels)]}")
    for (name, labels) in sorted(summaries):
        _header(name)
        count, total = summaries[(name, labels)]
        lbl = _fmt_labels(labels)
        lines.append(f"{name}_count{lbl} {count}")
        lines.append(f"{name}_sum{lbl} {total}")
    return "\n".join(lines) + ("\n" if lines else "")


# --- Convenience wrappers wired at chokepoints (all no-op when off) ---

def record_cost_metrics(
    *, provider: str, status: str, was_expensive: bool, cost_usd: float
) -> None:
    if status == "completed":
        inc("provider_call_total", provider=provider)
        if cost_usd:
            inc(
                "provider_estimated_cost_usd_total",
                float(cost_usd),
                provider=provider,
            )
    elif status == "failed":
        inc("provider_call_failed_total", provider=provider)
        log_event("provider_call_failed", provider=provider)
    elif status == "blocked" and was_expensive:
        inc("kimi_blocked_total", provider=provider)


def record_route_decision(selected_provider: str) -> None:
    inc("llm_route_decision_total", provider=selected_provider)


def record_runner_selected(runner: str) -> None:
    inc("runner_selected_total", runner=runner)


def observe_runner_duration(seconds: float, runner: str) -> None:
    observe("runner_duration_seconds", seconds, runner=runner)


def record_contextpack_tokens(before: int, after: int) -> None:
    inc("contextpack_tokens_before_total", float(max(0, before)))
    inc("contextpack_tokens_after_total", float(max(0, after)))


def record_workflow_started(workflow_type: str) -> None:
    inc("workflow_started_total", workflow=workflow_type)


def record_workflow_failed(workflow_type: str) -> None:
    inc("workflow_failed_total", workflow=workflow_type)
    log_event("workflow_failed", workflow=workflow_type)


def observe_approval_wait(seconds: float) -> None:
    observe("approval_wait_seconds", max(0.0, float(seconds)))


def record_provider_rate_limited(provider: str) -> None:
    inc("provider_rate_limited_total", provider=provider)


def record_cache_event(hit: bool) -> None:
    inc("cache_hit_total" if hit else "cache_miss_total")


def record_remediation_proposal(source_type: str) -> None:
    inc("remediation_proposal_total", source_type=source_type)


def observability_runtime_summary() -> dict:
    with _lock:
        series = len(_counters) + len(_summaries)
    return {
        "observability_enabled": _config.OBSERVABILITY_ENABLED,
        "metrics_enabled": _config.METRICS_ENABLED,
        "metrics_path": _config.METRICS_PATH,
        "structured_logs_enabled": _config.STRUCTURED_LOGS_ENABLED,
        "otel_enabled": _config.OTEL_ENABLED,
        "otel_status": "config_flag_only_not_implemented",
        "active_series": series,
        "is_source_of_truth": False,
    }


__all__ = [
    "inc",
    "observe",
    "log_event",
    "reset",
    "render",
    "record_cost_metrics",
    "record_route_decision",
    "record_runner_selected",
    "observe_runner_duration",
    "record_contextpack_tokens",
    "record_workflow_started",
    "record_workflow_failed",
    "observe_approval_wait",
    "observability_runtime_summary",
]
