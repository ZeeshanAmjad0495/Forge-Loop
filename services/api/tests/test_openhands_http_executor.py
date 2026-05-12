"""Tests for HttpOpenHandsExecutor — the HTTP-based bridge to an upstream
OpenHands container's ``/api/v1/app-conversations`` API.

These tests inject stub ``http_get`` / ``http_post`` callables, so no real
HTTP request, no docker container, and no live LLM is required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app import config
from app.services.openhands_execution import (
    HttpOpenHandsExecutor,
    OpenHandsHttpError,
    _build_default_executor,
    _summarize_events,
    SubprocessOpenHandsExecutor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubHttp:
    """Records calls; returns scripted responses based on URL substring."""

    def __init__(self, *, start_task_id="task-abc", conv_id="conv-xyz",
                 events_count_sequence=None, events=None,
                 start_task_status="READY"):
        self.posts: list[dict] = []
        self.gets: list[dict] = []
        self._start_task_id = start_task_id
        self._conv_id = conv_id
        # Default: 0 events on first count poll, then 2 events forever.
        self._count_seq = list(events_count_sequence or [0, 2, 2])
        self._events = events or []
        self._count_idx = 0
        self._start_task_status = start_task_status

    def post(self, url, body, *, timeout):
        self.posts.append({"url": url, "body": body, "timeout": timeout})
        # POST /app-conversations returns a start-task id, not the conv id.
        return {"id": self._start_task_id, "status": "WORKING"}

    def get(self, url, *, timeout):
        self.gets.append({"url": url, "timeout": timeout})
        if "/start-tasks/search" in url:
            return {
                "items": [
                    {
                        "id": self._start_task_id,
                        "app_conversation_id": self._conv_id,
                        "status": self._start_task_status,
                    }
                ]
            }
        if "/events/count" in url:
            if self._count_idx < len(self._count_seq):
                val = self._count_seq[self._count_idx]
                self._count_idx += 1
            else:
                val = self._count_seq[-1] if self._count_seq else 0
            return val
        if "/events/search" in url:
            return {"items": list(self._events), "next_page_id": None}
        raise OpenHandsHttpError(f"unexpected GET {url}")


def _make_instruction_file(tmp_path: Path) -> Path:
    p = tmp_path / "instruction.json"
    p.write_text(json.dumps({"task": "tiny smoke", "instructions": ["do X"]}))
    return p


def _executor(stub: _StubHttp, **kwargs) -> HttpOpenHandsExecutor:
    return HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        quiet_after_seconds=0.0,
        http_get=stub.get,
        http_post=stub.post,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_run_returns_error_when_no_instruction_file_in_args(tmp_path):
    stub = _StubHttp()
    ex = _executor(stub)
    result = ex.run(
        command="ignored",
        args=["--flag", "nothing.json"],  # path doesn't exist
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )
    assert result.exit_code is None
    assert result.error == "instruction file not found in args"
    # No HTTP traffic was attempted
    assert stub.posts == []
    assert stub.gets == []


def test_run_posts_instruction_and_returns_agent_reply(tmp_path):
    instr = _make_instruction_file(tmp_path)
    agent_message = {
        "kind": "MessageEvent",
        "source": "agent",
        "content": [{"type": "text", "text": "OK"}],
    }
    user_message = {
        "kind": "MessageEvent",
        "source": "user",
        "content": [{"type": "text", "text": "Reply OK."}],
    }
    stub = _StubHttp(
        events_count_sequence=[0, 2, 2, 2],
        events=[user_message, agent_message],
    )
    ex = _executor(stub)

    result = ex.run(
        command="ignored",
        args=["--instructions", str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stdout == "OK"
    assert result.stderr == ""
    # One POST to start the conversation, with the instruction file content
    assert len(stub.posts) == 1
    post = stub.posts[0]
    assert post["url"].endswith("/api/v1/app-conversations")
    text_block = post["body"]["initial_message"]["content"][0]["text"]
    assert "tiny smoke" in text_block  # instruction file contents flowed through
    # At least one count poll + one events search
    assert any("/events/count" in g["url"] for g in stub.gets)
    assert any("/events/search" in g["url"] for g in stub.gets)


def test_run_handles_failure_response_from_post(tmp_path):
    instr = _make_instruction_file(tmp_path)

    def boom(url, body, *, timeout):
        raise OpenHandsHttpError("HTTP 500 from /api/v1/app-conversations: boom")

    ex = HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        quiet_after_seconds=0.0,
        http_post=boom,
        http_get=lambda *a, **kw: 0,
    )
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=2,
        max_output_bytes=1000,
    )
    assert result.exit_code is None
    assert result.timed_out is False
    assert "could not start OpenHands conversation" in (result.error or "")


def test_run_times_out_when_events_never_arrive(tmp_path):
    instr = _make_instruction_file(tmp_path)
    # Count stays 0 forever
    stub = _StubHttp(events_count_sequence=[0, 0, 0, 0, 0, 0], events=[])
    ex = HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        quiet_after_seconds=0.5,
        http_get=stub.get,
        http_post=stub.post,
    )
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=1,  # short deadline
        max_output_bytes=1000,
    )
    assert result.timed_out is True
    assert result.exit_code is None
    assert "timed out" in (result.error or "")


def test_run_returns_exit_code_1_when_error_event_present(tmp_path):
    instr = _make_instruction_file(tmp_path)
    error_event = {
        "kind": "AgentErrorEvent",
        "source": "agent",
        "error": "llm provider rejected request",
    }
    stub = _StubHttp(events_count_sequence=[0, 1, 1, 1], events=[error_event])
    ex = _executor(stub)

    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )
    assert result.exit_code == 1
    assert "llm provider rejected request" in result.stderr


def test_summarize_events_extracts_nested_llm_message_content():
    # OpenHands 1.x event shape: agent text is under ``llm_message.content``
    events = [
        {
            "kind": "MessageEvent",
            "source": "agent",
            "llm_message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "OK done"}],
            },
        }
    ]
    agent, err = _summarize_events(events)
    assert agent == "OK done"
    assert err == ""


def test_summarize_events_extracts_agent_text_and_errors():
    events = [
        {"kind": "MessageEvent", "source": "user", "content": [{"type": "text", "text": "hi"}]},
        {"kind": "MessageEvent", "source": "agent", "content": [{"type": "text", "text": "hello"}]},
        {"kind": "MessageEvent", "source": "agent", "content": [{"type": "text", "text": "world"}]},
        {"kind": "AgentErrorEvent", "source": "agent", "error": "oops"},
    ]
    agent, err = _summarize_events(events)
    assert agent == "hello\nworld"
    assert "oops" in err


# ---------------------------------------------------------------------------
# Factory test
# ---------------------------------------------------------------------------


def test_factory_returns_subprocess_by_default(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTOR", "subprocess")
    ex = _build_default_executor()
    assert isinstance(ex, SubprocessOpenHandsExecutor)


def test_factory_returns_http_when_configured(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTOR", "http")
    ex = _build_default_executor()
    assert isinstance(ex, HttpOpenHandsExecutor)


def test_factory_falls_back_to_subprocess_on_unknown(monkeypatch):
    monkeypatch.setattr(config, "OPENHANDS_EXECUTOR", "totally-unknown")
    ex = _build_default_executor()
    assert isinstance(ex, SubprocessOpenHandsExecutor)
