"""Agnostic Hook system for the Universal Orchestrator.

Allows registering callbacks for tool lifecycle events without depending on 
specific model SDKs (like claude_agent_sdk).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, TypeAlias

HookEvent = Literal[
    "PreToolUse", 
    "PostToolUse", 
    "PostToolUseFailure", 
    "PreCompact",
    "SubagentStart",
    "SubagentStop"
]

# Generic hook callback signature: 
# (input_data: dict, tool_use_id: str | None, context: Any) -> Awaitable[dict]
HookCallback: TypeAlias = Callable[[dict[str, Any], str | None, Any], Awaitable[dict[str, Any]]]

@dataclass(frozen=True)
class HookMatcher:
    """Matches a hook event to a set of callbacks, optionally filtering by tool name."""
    hooks: list[HookCallback] = field(default_factory=list)
    matcher: str | None = None  # Regex pattern for tool names

    def matches(self, tool_name: str | None) -> bool:
        """Returns True if the tool_name matches the regex pattern (or if no pattern)."""
        if self.matcher is None:
            return True
        if tool_name is None:
            return False
        return bool(re.search(self.matcher, tool_name))
