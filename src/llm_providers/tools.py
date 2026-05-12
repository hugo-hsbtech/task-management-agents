"""Vendor-neutral tool and MCP shapes.

Translated by each provider's _translate_tools / _translate_mcp hook into
the native SDK form. Providers that don't support a given concept raise
UnsupportedCapabilityError via require_capability().
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping  # noqa: TC003
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolSpec:
    """A vendor-neutral tool/function declaration.

    For in-process tools (handler is not None), the provider wires the
    handler into its tool-call dispatch. For declaration-only tools
    (handler is None), the provider only exposes the schema to the model.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]] | None = None


@dataclass(frozen=True)
class ToolPolicy:
    """Whitelist / denylist + custom tool declarations.

    `allowed` and `denied` use vendor-neutral tool names. Provider translates
    to the SDK's allowed_tools mechanism. `custom` lets the caller declare
    function-calling tools without going through MCP.
    """

    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    custom: tuple[ToolSpec, ...] = ()


@dataclass(frozen=True)
class McpServerSpec:
    """An MCP server registration.

    `transport="stdio"` requires `command`; `transport="http"` requires `url`.
    Validation is done by the provider's _translate_mcp hook.
    """

    name: str
    transport: Literal["stdio", "http"]
    command: tuple[str, ...] | None = None
    url: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
