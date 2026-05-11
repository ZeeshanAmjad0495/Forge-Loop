"""Task 38: narrow GitHub client.

Exposes exactly one method — ``create_draft_pull_request`` — and uses
stdlib ``urllib.request`` so no third-party HTTP dependency is added.
Tests monkeypatch the module-level singleton ``GITHUB_CLIENT``.

The client never lists, comments, reviews, merges, labels, assigns,
requests reviews, or fetches PRs. It does one thing: POST a draft PR.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .. import config as _config


class GitHubError(RuntimeError):
    """Generic GitHub error. ``status`` may be None for transport errors."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class GitHubAuthError(GitHubError):
    """401/403 — token missing/invalid/insufficient scopes."""


class GitHubNotFoundError(GitHubError):
    """404 — owner/repo not found or token lacks read access."""


class GitHubValidationError(GitHubError):
    """422 — payload rejected (e.g. PR already exists)."""


@dataclass(frozen=True)
class CreatedPullRequest:
    number: int
    url: str        # html_url
    api_url: str    # url (REST URL)
    state: str
    draft: bool
    head: str
    base: str
    title: str


class GitHubClient(Protocol):
    def create_draft_pull_request(
        self,
        *,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
        token: str,
    ) -> CreatedPullRequest: ...


def _redact_authorization(text: str) -> str:
    """Best-effort scrubbing of Authorization headers from error text."""
    if not text:
        return text or ""
    out = text
    for marker in ("Authorization: Bearer ", "Authorization: token ", "Bearer "):
        idx = 0
        while True:
            pos = out.lower().find(marker.lower(), idx)
            if pos == -1:
                break
            # Replace until next whitespace / quote / newline.
            end = pos + len(marker)
            stop = end
            while stop < len(out) and out[stop] not in (" ", "\n", "\r", "\"", "'", ","):
                stop += 1
            out = out[:end] + "***" + out[stop:]
            idx = end + 3
    return out


class UrllibGitHubClient:
    """stdlib-only GitHub client. POSTs to /repos/{owner}/{repo}/pulls."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: int | None = None,
        max_response_bytes: int | None = None,
    ) -> None:
        self._base_url = (base_url or _config.GITHUB_API_BASE_URL).rstrip("/")
        self._timeout = int(timeout if timeout is not None else _config.GITHUB_REQUEST_TIMEOUT_SECONDS)
        self._max_response = int(
            max_response_bytes if max_response_bytes is not None
            else _config.GITHUB_MAX_RESPONSE_BYTES
        )

    def create_draft_pull_request(
        self,
        *,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
        token: str,
    ) -> CreatedPullRequest:
        if not token:
            raise GitHubAuthError("GitHub token is empty")
        url = f"{self._base_url}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": bool(draft),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
        )
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "ForgeLoop")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read(self._max_response)
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read(self._max_response).decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            err_body = _redact_authorization(err_body)
            status = int(exc.code) if exc.code is not None else None
            message = f"GitHub returned {status}: {err_body[:1000]}"
            if status in (401, 403):
                raise GitHubAuthError(message, status=status) from None
            if status == 404:
                raise GitHubNotFoundError(message, status=status) from None
            if status == 422:
                raise GitHubValidationError(message, status=status) from None
            raise GitHubError(message, status=status) from None
        except urllib.error.URLError as exc:
            raise GitHubError(
                f"GitHub request failed: {_redact_authorization(str(exc.reason))}"
            ) from None

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GitHubError(f"could not parse GitHub response: {exc}") from None

        try:
            return CreatedPullRequest(
                number=int(parsed["number"]),
                url=str(parsed.get("html_url") or parsed.get("url") or ""),
                api_url=str(parsed.get("url") or ""),
                state=str(parsed.get("state") or "open"),
                draft=bool(parsed.get("draft", draft)),
                head=str(parsed.get("head", {}).get("ref") or head),
                base=str(parsed.get("base", {}).get("ref") or base),
                title=str(parsed.get("title") or title),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GitHubError(f"unexpected GitHub response shape: {exc}") from None


# Module-level singleton — tests monkeypatch this slot.
GITHUB_CLIENT: GitHubClient = UrllibGitHubClient()


__all__ = [
    "CreatedPullRequest",
    "GITHUB_CLIENT",
    "GitHubAuthError",
    "GitHubClient",
    "GitHubError",
    "GitHubNotFoundError",
    "GitHubValidationError",
    "UrllibGitHubClient",
]
