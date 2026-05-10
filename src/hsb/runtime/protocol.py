"""Runtime-agnostic Protocol and option shape.

These types are the lowest common denominator between claude_agent_sdk
and openai_codex_sdk. They are NOT re-exports of either SDK's types —
each Runtime implementation translates AgentOptions into its native
options at the seam.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from hsb.runtime.hooks import HookMatcher, HookEvent


PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]
RuntimeName = Literal["claude", "codex", "gemini"]


@dataclass(frozen=True)
class Message:
    """Minimal message shape both runtimes yield. Mirrors the surface
    Backlog Agent uses today (text accumulation + final-result detection).
    """
    text: str
    is_final: bool = False
    raw: Any = None  # underlying SDK message, for opt-in inspection


@dataclass(frozen=True)
class AgentOptions:
    """Runtime-agnostic option shape. Returned by make_agent_options()."""
    system_prompt: str
    allowed_tools: tuple[str, ...]
    permission_mode: PermissionMode
    max_turns: int
    model: str
    mcp_servers: dict[str, dict] | None = None
    cwd: str | None = None
    output_schema: dict | None = None
    hooks: dict[HookEvent, list[HookMatcher]] | None = None  # Agnostic Hook system


class StatefulClient(Protocol):
    """Future use — parallel to claude_agent_sdk.ClaudeSDKClient. Not used
    by the Backlog pilot. Concrete implementations land when WIO is ported.
    """
    async def __aenter__(self) -> "StatefulClient": ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def query(self, prompt: str) -> AsyncIterator[Message]: ...


class Runtime(Protocol):
    """Two implementations: ClaudeRuntime, CodexRuntime."""
    name: RuntimeName

    def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        """One-shot query — async iterator of Message events."""
        ...

    def client(self, options: AgentOptions) -> StatefulClient:
        """Stateful multi-turn client. Not used by Backlog; placeholder for WIO port."""
        ...
