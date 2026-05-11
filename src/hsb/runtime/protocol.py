"""Runtime-agnostic Protocol and option shape.

Historically the lowest common denominator between ``claude_agent_sdk`` and
``openai_codex_sdk``. The canonical home for vendor-neutral types is now
the :mod:`llm_providers` library — this module re-exports those types
where the field shapes line up, and keeps the legacy ``AgentOptions``
dataclass intact for callers (and tests) that still construct it with the
older field set.

Deprecation window:

* :data:`Message` is the library ``Message`` (identical fields — ``text``,
  ``is_final``, ``raw``).
* :data:`PermissionMode` is the library ``PermissionMode``
  (``Literal["default", "acceptEdits", "plan", "bypassPermissions"]``).
* :data:`Runtime` is aliased to :class:`llm_providers.base.BaseProvider`
  so ``isinstance(x, Runtime)`` works for new provider instances. The
  legacy compat shims (``ClaudeRuntime`` / ``CodexRuntime``) are
  structural duck-types and intentionally do not subclass
  ``BaseProvider``.
* :class:`AgentOptions` keeps the legacy field set
  (``system_prompt: str``, ``allowed_tools: tuple[str, ...]``,
  ``mcp_servers: dict | None``, ``hooks: Any``) so the compat shims and
  ``make_agent_options`` factory continue to work. Migration to
  ``ProviderOptions`` lands as part of Task 21+.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from llm_providers.base import BaseProvider as _BaseProvider
from llm_providers.protocol import Message as _LibMessage
from llm_providers.protocol import PermissionMode as _LibPermissionMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Re-exports from the library — identical shapes today.
Message = _LibMessage
PermissionMode = _LibPermissionMode

RuntimeName = Literal["claude", "codex"]


@dataclass(frozen=True)
class AgentOptions:
    """Legacy runtime-agnostic option shape returned by ``make_agent_options()``.

    Kept as a distinct dataclass during the deprecation window because the
    field set differs from :class:`llm_providers.protocol.ProviderOptions`
    (string ``system_prompt`` vs ``SystemPrompt`` sum type, ``dict``
    ``mcp_servers`` vs ``tuple[McpServerSpec, ...]``, plus a Claude-only
    ``hooks`` slot). New code should construct ``ProviderOptions``
    directly; the compat shims in :mod:`hsb.runtime.compat` translate
    instances of this class into each SDK's native shape.
    """

    system_prompt: str
    allowed_tools: tuple[str, ...]
    permission_mode: PermissionMode
    max_turns: int
    model: str
    mcp_servers: dict[str, dict] | None = None
    cwd: str | None = None
    output_schema: dict | None = None
    hooks: Any = None  # Claude-only HookMatcher list; CodexRuntime rejects non-None.


class StatefulClient(Protocol):
    """Future use — parallel to claude_agent_sdk.ClaudeSDKClient. Not used
    by the Backlog pilot. Concrete implementations land when WIO is ported.
    """

    async def __aenter__(self) -> StatefulClient: ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def query(self, prompt: str) -> AsyncIterator[Message]: ...


# Alias the legacy ``Runtime`` Protocol onto the library's ABC. Concrete
# subclasses of ``BaseProvider`` therefore satisfy ``isinstance(x, Runtime)``
# during the deprecation window. The structural duck-type shims in
# :mod:`hsb.runtime.compat` (``ClaudeRuntime`` / ``CodexRuntime``) do *not*
# subclass ``BaseProvider`` and are not expected to.
Runtime = _BaseProvider


__all__ = [
    "AgentOptions",
    "Message",
    "PermissionMode",
    "Runtime",
    "RuntimeName",
    "StatefulClient",
]
