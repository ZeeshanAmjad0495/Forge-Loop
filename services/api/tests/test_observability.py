"""Tests for C2: ObservabilityProvider + Langfuse backend.

No network: the Langfuse client is always injected or absent. Verifies the
hard guarantee that observability never breaks the cost-recording path.
"""

from __future__ import annotations

import pytest

from app import config
from app.repositories import InMemoryCostRecordRepository
from app.services import observability
from app.services.cost_tracking import record_cost


@pytest.fixture(autouse=True)
def _reset_provider():
    observability.reset_observability_provider()
    yield
    observability.reset_observability_provider()


class _FakeLangfuseClient:
    def __init__(self):
        self.generations: list[dict] = []

    def generation(self, **kwargs):
        self.generations.append(kwargs)


class _BoomClient:
    def generation(self, **kwargs):
        raise RuntimeError("langfuse down")


def test_default_provider_is_noop(monkeypatch):
    monkeypatch.setattr(config, "LANGFUSE_ENABLED", False)
    provider = observability.get_observability_provider()
    assert provider.name == "noop"
    # No-op accepts the call and returns None.
    assert provider.record_generation(
        name="x", provider="deepseek", model="m",
        input_tokens=1, output_tokens=2, total_tokens=3, cost_usd=0.0,
        project_id="p", source_type="agent_run", source_id="s",
    ) is None


def test_langfuse_selected_when_enabled_but_noop_without_creds(monkeypatch):
    monkeypatch.setattr(config, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(config, "LANGFUSE_SECRET_KEY", "")
    monkeypatch.setattr(config, "LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr(config, "LANGFUSE_HOST", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    provider = observability.get_observability_provider()
    assert provider.name == "langfuse"
    # Missing creds -> resolves to a permanent no-op, no exception.
    provider.record_generation(
        name="x", provider="deepseek", model="m",
        input_tokens=1, output_tokens=2, total_tokens=3, cost_usd=0.1,
        project_id="p", source_type="agent_run", source_id="s",
    )


def test_langfuse_emits_generation_with_injected_client():
    fake = _FakeLangfuseClient()
    provider = observability.LangfuseObservabilityProvider(client=fake)
    provider.record_generation(
        name="planning:agent_run",
        provider="deepseek",
        model="deepseek-chat",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        cost_usd=0.0042,
        project_id="proj-1",
        source_type="agent_run",
        source_id="run-9",
        metadata={"requirement_id": "req-3"},
    )
    assert len(fake.generations) == 1
    g = fake.generations[0]
    assert g["name"] == "planning:agent_run"
    assert g["model"] == "deepseek-chat"
    assert g["usage"] == {"input": 10, "output": 20, "total": 30, "unit": "TOKENS"}
    assert g["metadata"]["provider"] == "deepseek"
    assert g["metadata"]["project_id"] == "proj-1"
    assert g["metadata"]["estimated_cost_usd"] == 0.0042
    assert g["metadata"]["requirement_id"] == "req-3"


def test_langfuse_swallows_backend_errors():
    provider = observability.LangfuseObservabilityProvider(client=_BoomClient())
    # Must not raise even though the client throws.
    provider.record_generation(
        name="x", provider="p", model="m",
        input_tokens=1, output_tokens=1, total_tokens=2, cost_usd=0.0,
        project_id="p", source_type="agent_run", source_id="s",
    )


def test_record_cost_emits_to_observability_provider():
    fake = _FakeLangfuseClient()
    observability.set_observability_provider(
        observability.LangfuseObservabilityProvider(client=fake)
    )
    repo = InMemoryCostRecordRepository()
    rec = record_cost(
        repo,
        project_id="proj-1",
        source_type="agent_run",
        source_id="run-1",
        workflow_type="planning",
        provider="deepseek",
        model="deepseek-chat",
        input_tokens=100,
        output_tokens=50,
        estimated_input_cost_usd=0.01,
        estimated_output_cost_usd=0.02,
    )
    assert rec.total_tokens == 150
    assert len(fake.generations) == 1
    g = fake.generations[0]
    assert g["name"] == "planning:agent_run"
    assert g["usage"]["total"] == 150
    assert g["metadata"]["estimated_cost_usd"] == pytest.approx(0.03)


def test_record_cost_unaffected_when_observability_raises():
    """A broken observability backend must not break cost recording."""
    observability.set_observability_provider(
        observability.LangfuseObservabilityProvider(client=_BoomClient())
    )
    repo = InMemoryCostRecordRepository()
    rec = record_cost(
        repo,
        project_id="p",
        source_type="agent_run",
        source_id="s",
        workflow_type="planning",
        provider="deepseek",
        model="m",
        input_tokens=1,
        output_tokens=1,
    )
    assert rec.total_tokens == 2
