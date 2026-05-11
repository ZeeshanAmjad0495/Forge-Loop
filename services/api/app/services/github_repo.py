"""Repository URL → (owner, repo) parser for Task 38.

Accepts only canonical github.com URLs. Strict character validation; no
network. Wildcard / enterprise / *.github.com hosts are rejected in v1 —
the parser is conservative on purpose.
"""

from __future__ import annotations

import re


class GitHubRepoUrlError(ValueError):
    """Raised when ``parse_owner_repo`` cannot accept the URL."""


# GitHub permits names with letters, digits, ``.``/``_``/``-``. We require the
# first character to be alphanumeric and cap length at 100 characters.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

# https://github.com/<owner>/<repo>(.git)?(/)? — HTTPS only.
_HTTPS_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)
# git@github.com:<owner>/<repo>(.git)?
_SSH_SHORT_RE = re.compile(
    r"^git@github\.com:([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)
# ssh://git@github.com/<owner>/<repo>(.git)?
_SSH_LONG_RE = re.compile(
    r"^ssh://git@github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


def parse_owner_repo(repo_url: str | None) -> tuple[str, str]:
    """Return ``(owner, repo)`` for a GitHub URL, else raise.

    Accepts:
      - ``https://github.com/owner/repo``
      - ``https://github.com/owner/repo.git``
      - ``git@github.com:owner/repo(.git)?``
      - ``ssh://git@github.com/owner/repo(.git)?``

    Rejects: ``http://``, non-github hosts, single-segment paths, names
    containing ``..`` or shell metacharacters, empty owner/repo.
    """
    if not repo_url or not isinstance(repo_url, str):
        raise GitHubRepoUrlError("repo_url is empty")
    raw = repo_url.strip()
    if not raw:
        raise GitHubRepoUrlError("repo_url is empty")

    for pattern in (_HTTPS_RE, _SSH_SHORT_RE, _SSH_LONG_RE):
        m = pattern.match(raw)
        if m:
            owner, repo = m.group(1), m.group(2)
            if not _NAME_RE.match(owner):
                raise GitHubRepoUrlError("repo_url has an invalid owner name")
            if not _NAME_RE.match(repo):
                raise GitHubRepoUrlError("repo_url has an invalid repo name")
            if ".." in owner or ".." in repo:
                raise GitHubRepoUrlError("repo_url has forbidden '..' sequence")
            return owner, repo
    raise GitHubRepoUrlError(
        "unsupported repository URL for GitHub PR creation"
    )


__all__ = ["GitHubRepoUrlError", "parse_owner_repo"]
