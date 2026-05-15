"""Tool-runner adapter registry.

Maps a ``runner_type`` to its pure ``ToolRunner`` adapter. Adapters build
instruction packages and update ToolRun records; they never execute.
"""

from __future__ import annotations

from .aider import AiderRunner
from .openhands import OpenHandsRunner

_REGISTRY: dict[str, object] = {
    "openhands": OpenHandsRunner(),
    "aider": AiderRunner(),
}


def get_runner(runner_type: str):
    """Return the adapter for ``runner_type``, or None if unsupported."""
    return _REGISTRY.get(runner_type)


__all__ = ["AiderRunner", "OpenHandsRunner", "get_runner"]
