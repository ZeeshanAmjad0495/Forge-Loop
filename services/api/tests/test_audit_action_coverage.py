"""Guard: every audit action written in the codebase is a registered
``AuditAction`` literal.

A live OpenHands run 500'd because B1 wrote ``openhands_workspace_synced``
but never added it to the Literal — unit tests stubbed the audit writer so
it escaped. This static scan fails CI if any ``*.write("<action>", ...)``
first-arg string constant is missing from the Literal, killing the class.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def _registered_actions() -> set[str]:
    src = (APP / "models" / "audit.py").read_text()
    block = src.split("AuditAction = Literal[")[1].split("]")[0]
    return set(re.findall(r'"([a-z_]+)"', block))


def test_all_written_audit_actions_are_registered():
    registered = _registered_actions()
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            if name != "write" or not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant)
                    and isinstance(first.value, str)):
                continue
            action = first.value
            # Only audit-action-shaped literals (snake_case words).
            if not re.fullmatch(r"[a-z][a-z_]+", action):
                continue
            if action not in registered:
                offenders.append(
                    f"{path.relative_to(APP.parent)}: "
                    f"write({action!r}) not in AuditAction"
                )
    assert not offenders, "Unregistered audit actions:\n" + "\n".join(offenders)
