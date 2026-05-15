"""Tests for the Kody client envelope handling.

A live review surfaced this: Kodus wraps payloads in {"data": {...}}.
start_review only checked top-level jobId, so a PENDING job was misread as
a synchronous result and the review was falsely 'approved'. These lock the
unwrap behaviour (no network — _request is monkeypatched).
"""

from __future__ import annotations

from app.services.kody_client import UrllibKodyClient, _redact_key, _unwrap


def test_unwrap_strips_data_envelope():
    assert _unwrap({"data": {"jobId": "j1", "status": "PENDING"}}) == {
        "jobId": "j1", "status": "PENDING"
    }


def test_unwrap_passthrough_when_no_envelope():
    raw = {"summary": "ok", "issues": []}
    assert _unwrap(raw) == raw
    assert _unwrap({"data": {}}) == {"data": {}}  # empty data -> not unwrapped


def test_start_review_unwraps_job_envelope(monkeypatch):
    c = UrllibKodyClient(base_url="http://x")
    monkeypatch.setattr(
        c, "_request",
        lambda *a, **k: {"data": {"jobId": "c27", "status": "PENDING",
                                  "statusUrl": "/cli/review/jobs/c27"}},
    )
    out = c.start_review(api_key="kodus_k", diff="d")
    # Unwrapped -> the execution service can now detect the async job.
    assert out["jobId"] == "c27"
    assert out["status"] == "PENDING"


def test_get_review_job_unwraps_envelope(monkeypatch):
    c = UrllibKodyClient(base_url="http://x")
    monkeypatch.setattr(
        c, "_request",
        lambda *a, **k: {"data": {"status": "COMPLETED",
                                  "result": {"summary": "s", "issues": []}}},
    )
    out = c.get_review_job(api_key="kodus_k", job_id="c27")
    assert out["status"] == "COMPLETED"
    assert out["result"]["issues"] == []


def test_redact_key_still_scrubs():
    assert "kodus_abc" not in _redact_key("fail kodus_abc done", "kodus_abc")
