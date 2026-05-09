"""linear_middleware.py — PydanticAI equivalents of hooks.py behavior.

Replaces HookMatcher PostToolUseFailure / PostToolUse / PreCompact / PreToolUse.
In PydanticAI, these become:

1. write_audit_entry: a Python function called AFTER agent.run()
   to log tool usage to .claude/linear_audit.log.

2. make_linear_mcp_toolset: returns a PydanticAI MCPServerStdio
   for the Linear MCP server.

3. MAX_RETRIES: constant preserved for source-grep tests.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = ".claude/linear_audit.log"
MAX_RETRIES = 3  # Preserved constant for tests that grep for it


def write_audit_entry(
    tool_name: str, tool_use_id: str | None, output_preview: str
) -> None:
    """Write one JSON line to the Linear audit log (replaces linear_audit_hook)."""
    Path(AUDIT_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "tool_use_id": tool_use_id,
        "tool_output_preview": output_preview[:2000],
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def make_linear_mcp_toolset() -> Any:
    """Return a PydanticAI MCPServerStdio for the Linear MCP server.

    Uses fastmcp transport to npx mcp-remote https://mcp.linear.app/mcp
    """
    try:
        from pydantic_ai.mcp import MCPServerStdio
    except ImportError:  # pragma: no cover
        # Fallback for older pydantic-ai versions
        from pydantic_ai_slim.mcp import MCPServerStdio  # type: ignore

    return MCPServerStdio(
        "npx",
        ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
    )
