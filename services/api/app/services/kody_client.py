"""Kodus (Kody) CLI HTTP client.

Talks to the Kodus open-source backend's CLI-key API (the same surface the
`kody` CLI uses). Contract verified against kodustech/kodus-ai
`apps/api/src/controllers/cli/cli-review.controller.ts` + the cli-review
DTOs:

- Auth: a team CLI key (``kodus_...``) sent as ``x-team-key`` header.
- ``GET  {base}/cli/validate-key``      -> {valid, teamId, ...} | 401
- ``POST {base}/cli/review``            -> sync {summary, issues, ...}
  with header ``x-kodus-async: 1``      -> {jobId} (poll)
- ``GET  {base}/cli/review/jobs/{id}``  -> {status, result?, error?}

stdlib ``urllib`` only (no new dependency), mirroring the github_client
safety pattern: configurable timeout, bounded response read, typed error
hierarchy, and the team key scrubbed from any error text. The key is never
logged and is supplied per-call (resolved from the secret provider by the
caller), never read from a committed file here.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import config as _config


class KodyError(RuntimeError):
    """Generic Kodus error. ``status`` is None for transport errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class KodyAuthError(KodyError):
    """401/403 — team CLI key missing/invalid."""


class KodyNotFoundError(KodyError):
    """404 — unknown job id / route."""


class KodyValidationError(KodyError):
    """400/422 — request rejected (e.g. diff too large/empty)."""


class KodyRateLimitError(KodyError):
    """429 — Kodus rate limit hit."""


def _redact_key(text: str, key: str | None) -> str:
    """Scrub the team key (and any kodus_-prefixed token) from text."""
    out = text or ""
    if key:
        out = out.replace(key, "***")
    # Defensive: blank any remaining kodus_<token> run.
    while True:
        i = out.find("kodus_")
        if i == -1:
            break
        j = i + len("kodus_")
        while j < len(out) and (out[j].isalnum() or out[j] in "-_"):
            j += 1
        out = out[:i] + "***" + out[j:]
    return out


def _unwrap(resp: dict) -> dict:
    """Kodus wraps payloads in a ``{"data": {...}}`` envelope (observed on
    the live API; the OpenAPI DTOs don't show it). Unwrap one level so
    callers see ``{jobId, status, ...}`` / ``{summary, issues, ...}``
    directly. Idempotent for un-enveloped responses."""
    if isinstance(resp, dict):
        inner = resp.get("data")
        if isinstance(inner, dict) and inner:
            return inner
    return resp


class UrllibKodyClient:
    """stdlib-only Kodus CLI client."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: int | None = None,
        max_response_bytes: int | None = None,
    ) -> None:
        self._base_url = (base_url or _config.KODY_BASE_URL or "").rstrip("/")
        self._timeout = int(
            timeout if timeout is not None
            else _config.KODY_REQUEST_TIMEOUT_SECONDS
        )
        self._max_response = int(
            max_response_bytes if max_response_bytes is not None
            else _config.KODY_MAX_RESPONSE_BYTES
        )

    # -- low-level ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        api_key: str,
        body: dict | None = None,
        extra_headers: dict | None = None,
    ) -> dict:
        if not self._base_url:
            raise KodyError("Kody base URL is not configured")
        if not api_key:
            raise KodyAuthError("Kody team CLI key is empty")
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("x-team-key", api_key)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for k, v in (extra_headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read(self._max_response)
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read(self._max_response).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                err_body = ""
            err_body = _redact_key(err_body, api_key)
            status = int(exc.code) if exc.code is not None else None
            msg = f"Kody returned {status}: {err_body[:1000]}"
            if status in (401, 403):
                raise KodyAuthError(msg, status=status) from None
            if status == 404:
                raise KodyNotFoundError(msg, status=status) from None
            if status == 429:
                raise KodyRateLimitError(msg, status=status) from None
            if status in (400, 422):
                raise KodyValidationError(msg, status=status) from None
            raise KodyError(msg, status=status) from None
        except urllib.error.URLError as exc:
            raise KodyError(
                f"Kody request failed: {_redact_key(str(exc.reason), api_key)}"
            ) from None
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise KodyError(
                f"could not parse Kody response: {exc}"
            ) from None
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    # -- public API --------------------------------------------------------

    def validate_key(self, *, api_key: str) -> dict:
        """GET /cli/validate-key. Raises KodyAuthError on an invalid key."""
        resp = self._request("GET", "/cli/validate-key", api_key=api_key)
        payload = resp.get("data", resp) if isinstance(resp, dict) else {}
        if not payload.get("valid", False):
            raise KodyAuthError(
                "Kody rejected the team CLI key: "
                f"{_redact_key(str(payload.get('error') or 'invalid'), api_key)}"
            )
        return payload

    def start_review(
        self,
        *,
        api_key: str,
        diff: str,
        config: dict | None = None,
        branch: str | None = None,
        commit_sha: str | None = None,
        merge_base_sha: str | None = None,
        git_remote: str | None = None,
        user_email: str | None = None,
        async_mode: bool = True,
    ) -> dict:
        """POST /cli/review. Returns {'jobId': ...} (async) or the sync
        review result {'summary','issues',...}."""
        payload: dict = {"diff": diff}
        if config is not None:
            payload["config"] = config
        if branch:
            payload["branch"] = branch
        if commit_sha:
            payload["commitSha"] = commit_sha
        if merge_base_sha:
            payload["mergeBaseSha"] = merge_base_sha
        if git_remote:
            payload["gitRemote"] = git_remote
        if user_email:
            payload["userEmail"] = user_email
        extra = {"x-kodus-async": "1"} if async_mode else None
        resp = self._request(
            "POST", "/cli/review",
            api_key=api_key, body=payload, extra_headers=extra,
        )
        return _unwrap(resp)

    def get_review_job(self, *, api_key: str, job_id: str) -> dict:
        """GET /cli/review/jobs/{jobId} -> {status, result?, error?}."""
        return _unwrap(
            self._request(
                "GET", f"/cli/review/jobs/{job_id}", api_key=api_key
            )
        )


KODY_CLIENT = UrllibKodyClient()


__all__ = [
    "KODY_CLIENT",
    "KodyAuthError",
    "KodyError",
    "KodyNotFoundError",
    "KodyRateLimitError",
    "KodyValidationError",
    "UrllibKodyClient",
    "_redact_key",
    "_unwrap",
]
