"""Tool/MCP shapes — see Task 4 for full implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPolicy:
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()


@dataclass(frozen=True)
class McpServerSpec:
    """Placeholder — see Task 4 for full implementation."""

    name: str
