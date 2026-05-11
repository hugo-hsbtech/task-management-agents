"""Core protocol types — minimal shape every provider satisfies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from llm_providers.prompt import SystemPrompt
    from llm_providers.tools import McpServerSpec, ToolPolicy


PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


@dataclass(frozen=True)
class Message:
    """Minimal message shape yielded by every provider's query() iterator."""

    text: str
    is_final: bool = False
    raw: Any = None


@dataclass(frozen=True)
class Capabilities:
    """Per-provider capability flags.

    Callers check these before requesting a feature; providers raise
    UnsupportedCapabilityError when a flag is False and the feature is
    exercised.
    """

    supports_mcp: bool
    supports_native_tools: bool
    supports_hooks: bool
    supports_stateful_client: bool
    supports_output_schema: bool
    supports_system_prompt_file: bool
    supports_streaming: bool
    max_context_tokens: int | None = None


@dataclass(frozen=True)
class ProviderOptions:
    """Vendor-neutral options.

    Translated to each provider's native shape by its _translate_* hooks.
    """

    system_prompt: SystemPrompt
    model: str
    max_turns: int
    tool_policy: ToolPolicy
    mcp_servers: tuple[McpServerSpec, ...] = ()
    permission_mode: PermissionMode = "default"
    output_schema: dict[str, Any] | None = None
    cwd: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)
