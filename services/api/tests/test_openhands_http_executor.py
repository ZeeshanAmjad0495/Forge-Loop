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
    _resolve_container_working_directory,
    _summarize_events,
    SubprocessOpenHandsExecutor,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubHttp:
    """Records calls; returns scripted responses based on URL substring."""

    def __init__(self, *, start_task_id="task-abc", conv_id="conv-xyz",
                 events_count_sequence=None, events=None,
                 start_task_status="READY",
                 execution_status_sequence=None,
                 omit_execution_status=False):
        self.posts: list[dict] = []
        self.gets: list[dict] = []
        self._start_task_id = start_task_id
        self._conv_id = conv_id
        # Default: 0 events on first count poll, then 2 events forever.
        self._count_seq = list(events_count_sequence or [0, 2, 2])
        self._events = events or []
        self._count_idx = 0
        self._start_task_status = start_task_status
        # Default: status stays "running" forever. Override per test to
        # exercise the new execution_status exit path.
        self._exec_seq = list(execution_status_sequence or ["running"])
        self._exec_idx = 0
        self._omit_execution_status = omit_execution_status

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
        if "/api/v1/app-conversations?ids=" in url:
            if self._exec_idx < len(self._exec_seq):
                status = self._exec_seq[self._exec_idx]
                self._exec_idx += 1
            else:
                status = self._exec_seq[-1] if self._exec_seq else "running"
            item: dict = {"id": self._conv_id}
            if not self._omit_execution_status:
                item["execution_status"] = status
            return {"items": [item]}
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


def test_run_records_phase_timing_breakdown(tmp_path):
    """B3: the bridge attributes wall time to sandbox-resolve vs agent-run
    so real runs yield a hard latency breakdown instead of one opaque total.
    """
    instr = _make_instruction_file(tmp_path)
    agent_message = {
        "kind": "MessageEvent",
        "source": "agent",
        "content": [{"type": "text", "text": "done"}],
    }
    stub = _StubHttp(events_count_sequence=[0, 1, 1, 1], events=[agent_message])
    ex = _executor(stub)

    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )

    assert result.exit_code == 0
    assert result.resolve_seconds >= 0.0
    assert result.run_seconds >= 0.0
    # The two phases reconstruct the total (within timing slack).
    assert abs(
        (result.resolve_seconds + result.run_seconds) - result.duration_seconds
    ) < 0.5


def test_resolve_timeout_is_configurable_and_attributed(tmp_path, monkeypatch):
    """B3 fix: start-task->READY (runtime spin-up) is no longer hard-capped
    at 120s; the cap is configurable and a resolve timeout is attributed to
    the resolve phase (was reported as resolve_seconds=0.0)."""
    from app import config

    monkeypatch.setattr(
        config, "OPENHANDS_HTTP_RESOLVE_TIMEOUT_SECONDS", 0.05
    )
    instr = _make_instruction_file(tmp_path)
    # conv_id=None -> start-task never yields an app_conversation_id, so the
    # runtime never becomes resolvable: the resolve loop must hit the cap.
    stub = _StubHttp(conv_id=None, start_task_status="PENDING")
    ex = _executor(stub)
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=900,  # large job timeout; resolve cap must bound it
        max_output_bytes=1000,
    )
    assert result.timed_out is True
    assert result.exit_code is None
    assert result.resolve_seconds > 0.0          # attributed, not 0.0
    assert result.run_seconds == 0.0
    assert "resolve cap" in (result.error or "")


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


def test_run_returns_exit_code_0_when_agent_completed_silently_via_tools(tmp_path):
    """If the agent finished via tool actions (file edits, bash, etc.) and
    emitted no closing text message, we still treat the conversation as a
    success as long as no error events were seen. ForgeLoop's workspace diff
    is the authoritative signal for "what changed"; the executor must not
    contradict it just because the agent didn't send a final chat reply.
    """
    instr = _make_instruction_file(tmp_path)
    silent_events = [
        {"kind": "MessageEvent", "source": "user",
         "content": [{"type": "text", "text": "Create OPENHANDS_MOUNT_SMOKE.txt"}]},
        {"kind": "ActionEvent", "source": "agent",
         "action": {"kind": "FileEditorAction", "command": "create",
                    "path": "/workspace/project/OPENHANDS_MOUNT_SMOKE.txt"}},
        {"kind": "ObservationEvent", "source": "environment",
         "observation": {"kind": "FileEditorObservation", "is_error": False}},
    ]
    stub = _StubHttp(
        events_count_sequence=[0, 3, 3, 3],
        events=silent_events,
    )
    ex = _executor(stub)
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )
    assert result.exit_code == 0
    assert result.timed_out is False
    # No agent text was emitted; stdout may be empty but that's OK
    assert result.stdout == ""
    assert result.stderr == ""


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


def test_run_exits_early_when_execution_status_reaches_terminal(tmp_path):
    """When the upstream conversation reports a terminal execution_status,
    the executor must exit immediately even if events/count never goes
    quiet for the full quiet_after window.
    """
    instr = _make_instruction_file(tmp_path)
    # Count keeps changing on every poll, so quiet-after never fires.
    stub = _StubHttp(
        events_count_sequence=[1, 2, 3, 4, 5, 6, 7, 8],
        events=[{"kind": "MessageEvent", "source": "agent",
                 "content": [{"type": "text", "text": "done"}]}],
        # 2 polls of "running", then "finished" — executor should exit here.
        execution_status_sequence=["running", "running", "finished"],
    )
    ex = HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        # Large quiet_after to prove it isn't what's ending the run.
        quiet_after_seconds=3600.0,
        http_get=stub.get,
        http_post=stub.post,
    )
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=60,
        max_output_bytes=1000,
    )
    assert result.exit_code == 0
    assert result.timed_out is False
    # Confirm the executor actually called the new endpoint.
    assert any("/api/v1/app-conversations?ids=" in g["url"] for g in stub.gets)


def test_run_falls_back_to_quiet_after_when_status_field_absent(tmp_path):
    """Older OpenHands builds may omit ``execution_status``. The executor
    must still exit via the event-count quiet-after heuristic.
    """
    instr = _make_instruction_file(tmp_path)
    stub = _StubHttp(
        events_count_sequence=[0, 2, 2, 2, 2, 2],
        events=[{"kind": "MessageEvent", "source": "agent",
                 "content": [{"type": "text", "text": "ok"}]}],
        omit_execution_status=True,
    )
    ex = HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        quiet_after_seconds=0.0,
        http_get=stub.get,
        http_post=stub.post,
    )
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )
    assert result.exit_code == 0
    assert result.timed_out is False


def test_run_treats_failed_execution_status_as_terminal(tmp_path):
    """A ``failed`` execution_status must also end polling. Whether the
    synthesized exit_code is 0 or 1 depends on event content (presence of
    error events); this test only asserts that the loop ends and emits no
    timeout.
    """
    instr = _make_instruction_file(tmp_path)
    stub = _StubHttp(
        events_count_sequence=[1, 2, 3, 4, 5],
        events=[{"kind": "AgentErrorEvent", "source": "agent",
                 "error": "agent gave up"}],
        execution_status_sequence=["running", "failed"],
    )
    ex = HttpOpenHandsExecutor(
        base_url="http://test.invalid:3000",
        poll_interval_seconds=0.0,
        quiet_after_seconds=3600.0,
        http_get=stub.get,
        http_post=stub.post,
    )
    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=60,
        max_output_bytes=1000,
    )
    assert result.timed_out is False
    assert "agent gave up" in result.stderr


def test_run_prepends_working_directory_directive_and_sends_title(tmp_path):
    instr = _make_instruction_file(tmp_path)
    stub = _StubHttp(
        events_count_sequence=[0, 1, 1, 1],
        events=[{"kind": "MessageEvent", "source": "agent",
                 "content": [{"type": "text", "text": "done"}]}],
    )
    ex = _executor(stub)

    result = ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
        working_directory="/workspace/projects/ProbePilot",
        title="Project skeleton",
    )

    assert result.exit_code == 0
    assert len(stub.posts) == 1
    body = stub.posts[0]["body"]
    text = body["initial_message"]["content"][0]["text"]
    assert text.startswith("Your working directory for this task is `/workspace/projects/ProbePilot`")
    assert "tiny smoke" in text  # original instruction file content still flows through
    assert body.get("title") == "Project skeleton"


def test_resolve_container_working_directory_returns_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENHANDS_HOST_PARENT_MOUNT", "")
    monkeypatch.setattr(config, "OPENHANDS_CONTAINER_PARENT_MOUNT", "")
    assert _resolve_container_working_directory(tmp_path.resolve()) is None


def test_resolve_container_working_directory_maps_subpath(monkeypatch, tmp_path):
    parent = tmp_path
    project = parent / "ProbePilot"
    project.mkdir()
    monkeypatch.setattr(config, "OPENHANDS_HOST_PARENT_MOUNT", str(parent))
    monkeypatch.setattr(config, "OPENHANDS_CONTAINER_PARENT_MOUNT", "/workspace/projects")
    assert (
        _resolve_container_working_directory(project.resolve())
        == "/workspace/projects/ProbePilot"
    )


def test_resolve_container_working_directory_rejects_outside_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENHANDS_HOST_PARENT_MOUNT", str(tmp_path / "inside"))
    monkeypatch.setattr(config, "OPENHANDS_CONTAINER_PARENT_MOUNT", "/workspace/projects")
    (tmp_path / "inside").mkdir()
    (tmp_path / "outside").mkdir()
    with pytest.raises(HTTPException) as exc:
        _resolve_container_working_directory((tmp_path / "outside").resolve())
    assert exc.value.status_code == 400
    assert "not inside" in exc.value.detail


def test_resolve_container_working_directory_rejects_partial_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPENHANDS_HOST_PARENT_MOUNT", str(tmp_path))
    monkeypatch.setattr(config, "OPENHANDS_CONTAINER_PARENT_MOUNT", "")
    with pytest.raises(HTTPException) as exc:
        _resolve_container_working_directory(tmp_path.resolve())
    assert exc.value.status_code == 400


def test_run_omits_directive_and_title_when_not_provided(tmp_path):
    instr = _make_instruction_file(tmp_path)
    stub = _StubHttp(
        events_count_sequence=[0, 1, 1, 1],
        events=[{"kind": "MessageEvent", "source": "agent",
                 "content": [{"type": "text", "text": "ok"}]}],
    )
    ex = _executor(stub)
    ex.run(
        command="ignored",
        args=[str(instr)],
        cwd=str(tmp_path),
        timeout_seconds=5,
        max_output_bytes=1000,
    )
    body = stub.posts[0]["body"]
    text = body["initial_message"]["content"][0]["text"]
    assert not text.startswith("Your working directory")
    assert "title" not in body
