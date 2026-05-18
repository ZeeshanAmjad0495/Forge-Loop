"""Task 84: CLI-first ForgeLoop client.

Standard-library only (argparse + urllib) so it runs anywhere the API
does, with zero extra dependencies. Thin wrappers over the real HTTP
API — no business logic here. Supports --dry-run (print the request,
send nothing) and --help on every command.

Usage:
    export FORGELOOP_API_URL=http://localhost:8080
    python -m app.cli login --email admin@example.com --password ...
    export FORGELOOP_TOKEN=<token from login>
    python -m app.cli create-project --name Demo --description "..."
    python -m app.cli cost --project <id>
    python -m app.cli approvals --project <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:8080"


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    token: str | None = None,
    base_url: str,
    dry_run: bool = False,
) -> dict:
    url = base_url.rstrip("/") + path
    plan = {"method": method, "url": url, "body": body}
    if dry_run:
        return {"dry_run": True, **plan}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 (local API)
            raw = resp.read().decode()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        return {"error": exc.code, "detail": detail}
    except urllib.error.URLError as exc:
        return {"error": "connection", "detail": str(exc.reason)}


# Each command: (method, path_template, body_keys). path uses {arg}.
_COMMANDS: dict[str, tuple[str, str, list[str]]] = {
    "login": ("POST", "/auth/login", ["email", "password"]),
    "whoami": ("GET", "/auth/me", []),
    "create-project": ("POST", "/projects", ["name", "description"]),
    "list-projects": ("GET", "/projects", []),
    "create-ticket": (
        "POST", "/projects/{project}/tickets", ["title", "description"]
    ),
    "create-requirement": (
        "POST",
        "/projects/{project}/requirements",
        ["title", "description"],
    ),
    "generate-plan": (
        "POST", "/tickets/{ticket}/planning-runs", ["provider"]
    ),
    "create-dev-tasks": (
        "POST", "/tickets/{ticket}/task-decompositions", ["provider"]
    ),
    "request-approval": (
        "POST",
        "/approvals",
        ["project_id", "target_type", "target_id"],
    ),
    "decide-approval": (
        "PATCH", "/approvals/{approval}", ["status", "feedback"]
    ),
    "approvals": ("GET", "/projects/{project}/approvals", []),
    "list-tickets": ("GET", "/projects/{project}/tickets", []),
    "dev-tasks": ("GET", "/projects/{project}/dev-tasks", []),
    "events": ("GET", "/projects/{project}/audit-events", []),
    "jobs": ("GET", "/projects/{project}/jobs", []),
    "providers": ("GET", "/llm/providers", []),
    "worker-run-once": ("POST", "/jobs/worker/run-once", []),
    "runner-preview": (
        "POST", "/projects/{project}/runner-route/preview", []
    ),
    "model-route-preview": (
        "POST", "/projects/{project}/model-route/preview", []
    ),
    "cost": ("GET", "/projects/{project}/cost-report", []),
    "runtime": ("GET", "/runtime/{topic}", []),
}

# path params each command needs (besides body keys).
_PATH_ARGS: dict[str, list[str]] = {
    "create-ticket": ["project"],
    "create-requirement": ["project"],
    "generate-plan": ["ticket"],
    "create-dev-tasks": ["ticket"],
    "decide-approval": ["approval"],
    "approvals": ["project"],
    "list-tickets": ["project"],
    "dev-tasks": ["project"],
    "events": ["project"],
    "jobs": ["project"],
    "runner-preview": ["project"],
    "model-route-preview": ["project"],
    "cost": ["project"],
    "runtime": ["topic"],
}


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    # default=SUPPRESS: an unspecified flag is absent from the namespace,
    # so the same flag can be added to BOTH the top-level parser and each
    # subparser without one clobbering the other. This lets global flags
    # be passed either before OR after the subcommand (the natural,
    # documented order). Env fallback is applied in main(), not here.
    parser.add_argument(
        "--base-url",
        default=argparse.SUPPRESS,
        help="API base URL (env FORGELOOP_API_URL).",
    )
    parser.add_argument(
        "--token",
        default=argparse.SUPPRESS,
        help="Bearer token (env FORGELOOP_TOKEN).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print the request that would be sent; send nothing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Emit raw JSON instead of the human-readable summary.",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forgeloop",
        description="CLI-first ForgeLoop client (stdlib only).",
    )
    _add_global_args(p)  # accepted before the subcommand
    sub = p.add_subparsers(dest="command", required=True)
    for name, (_method, _path, body_keys) in _COMMANDS.items():
        sp = sub.add_parser(name, help=f"{_method} {_path}")
        _add_global_args(sp)  # ...and after it
        for arg in _PATH_ARGS.get(name, []):
            sp.add_argument(f"--{arg}", required=True)
        for key in body_keys:
            required = name in ("login",) and key in (
                "email",
                "password",
            )
            sp.add_argument(f"--{key}", required=required)
    return p


def _resolve(name: str, args: argparse.Namespace) -> tuple[str, str, dict]:
    method, path_tmpl, body_keys = _COMMANDS[name]
    fmt = {a: getattr(args, a) for a in _PATH_ARGS.get(name, [])}
    path = path_tmpl.format(**fmt)
    body: dict | None = None
    if method in ("POST", "PATCH"):
        body = {
            k: getattr(args, k)
            for k in body_keys
            if getattr(args, k, None) is not None
        }
    return method, path, body  # type: ignore[return-value]


def _fmt_row(item: object) -> str:
    if isinstance(item, dict):
        # Prefer the few fields a human scans for; fall back to all.
        keys = [
            k
            for k in ("id", "name", "title", "status", "provider",
                      "job_type", "action", "conclusion", "created_at")
            if k in item
        ] or list(item)[:6]
        return "  ".join(f"{k}={item[k]}" for k in keys)
    return str(item)


def render_human(result: object) -> str:
    if isinstance(result, dict) and result.get("error"):
        return f"ERROR: {result.get('error')}"
    if isinstance(result, list):
        if not result:
            return "(empty)"
        return "\n".join(_fmt_row(i) for i in result)
    if isinstance(result, dict):
        return "\n".join(f"{k}: {v}" for k, v in result.items())
    return str(result)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Globals work in either position; env is the fallback.
    base_url = getattr(args, "base_url", None) or os.getenv(
        "FORGELOOP_API_URL", DEFAULT_URL
    )
    token = getattr(args, "token", None) or os.getenv("FORGELOOP_TOKEN")
    dry_run = getattr(args, "dry_run", False)
    as_json = getattr(args, "json", False)
    method, path, body = _resolve(args.command, args)
    result = _request(
        method,
        path,
        body=body,
        token=token,
        base_url=base_url,
        dry_run=dry_run,
    )
    # Dry-run always prints the raw request envelope (machine/debug
    # contract). Real results default to a human-readable summary;
    # --json restores raw JSON.
    if dry_run or as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_human(result))
    if args.command == "login" and not dry_run:
        tok = result.get("access_token")
        if tok:
            print(
                f"\n# export FORGELOOP_TOKEN={tok}",
                file=sys.stderr,
            )
    return 1 if isinstance(result, dict) and result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
