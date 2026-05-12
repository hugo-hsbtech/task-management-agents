"""Claude Agent SDK lifecycle hooks for Linear MCP tool calls.

Implements LINR-05 (exponential backoff + audit log) and prevents:
- Pitfall 3 (retry storm) via MAX_RETRIES=3 cap
- Pitfall 4 (context overflow) via enforce_list_filters PreToolUse hook
- Pitfall 6 (lost transcript) via pre_compact_handler PreCompact hook
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import (
    AsyncHookJSONOutput,
    HookContext,
    HookEvent,
    NotificationHookInput,
    PermissionRequestHookInput,
    PostToolUseFailureHookInput,
    PostToolUseHookInput,
    PreCompactHookInput,
    PreToolUseHookInput,
    StopHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
    SyncHookJSONOutput,
    UserPromptSubmitHookInput,
)

# Module-level retry counter; keyed by tool_use_id (or tool_name as fallback)
_retry_counts: dict[str, int] = {}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0
AUDIT_LOG_PATH = ".claude/linear_audit.log"


_HookInput = (
    PreToolUseHookInput
    | PostToolUseHookInput
    | PostToolUseFailureHookInput
    | UserPromptSubmitHookInput
    | StopHookInput
    | SubagentStopHookInput
    | PreCompactHookInput
    | NotificationHookInput
    | SubagentStartHookInput
    | PermissionRequestHookInput
)


async def linear_retry_hook(
    input_data: _HookInput, tool_use_id: str | None, context: HookContext
) -> AsyncHookJSONOutput | SyncHookJSONOutput:
    """PostToolUseFailure: exponential backoff for mcp__linear__* failures.

    Implements LINR-05 retry semantics: delays 1s, 2s, 4s; cap at 3 attempts.
    """
    raw: dict[str, Any] = cast("dict[str, Any]", input_data)
    tool_name: str = raw.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}

    key = tool_use_id or tool_name
    retry_count = _retry_counts.get(key, 0)

    if retry_count >= MAX_RETRIES:
        _retry_counts.pop(key, None)
        return {
            "systemMessage": (
                f"Linear tool {tool_name} failed after {MAX_RETRIES} retries. "
                "Do not retry. Return status='failed' with error_type='tool_failure'."
            )
        }

    delay = BASE_DELAY_SECONDS * (2**retry_count)
    _retry_counts[key] = retry_count + 1
    await asyncio.sleep(delay)

    return {
        "systemMessage": (
            f"Linear tool {tool_name} failed (attempt {retry_count + 1}/{MAX_RETRIES}). "
            f"Waited {delay:.0f}s. Retry the same tool call now."
        )
    }


async def linear_audit_hook(
    input_data: _HookInput, tool_use_id: str | None, context: HookContext
) -> AsyncHookJSONOutput | SyncHookJSONOutput:
    """PostToolUse: append a JSON line to .claude/linear_audit.log per Linear call.

    Logs tool name + truncated output. Clears retry counter on success.
    Per LINR-05, the agent's system prompt is responsible for ensuring updatedAt
    is captured pre/post-write — the audit log records whatever the tool returned.
    """
    raw: dict[str, Any] = cast("dict[str, Any]", input_data)
    tool_name: str = raw.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}

    if tool_use_id:
        _retry_counts.pop(tool_use_id, None)

    Path(AUDIT_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

    output = raw.get("tool_output", {})
    # Truncate large outputs so the audit log stays bounded
    output_repr = (
        json.dumps(output)[:2000] if not isinstance(output, str) else output[:2000]
    )

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool_name,
        "tool_use_id": tool_use_id,
        "tool_output_preview": output_repr,
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {}


async def pre_compact_handler(
    input_data: _HookInput, tool_use_id: str | None, context: HookContext
) -> AsyncHookJSONOutput | SyncHookJSONOutput:
    """PreCompact: archive transcript and instruct agent to re-read Linear state.

    Prevents Pitfall 6 (silent context loss during auto-compaction).
    """
    raw: dict[str, Any] = cast("dict[str, Any]", input_data)
    transcript_path: str | None = raw.get("transcript_path")
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    archive_path = f".claude/compaction_archive_{ts}.jsonl"
    if transcript_path:
        with contextlib.suppress(FileNotFoundError, PermissionError):
            shutil.copy(transcript_path, archive_path)
    return {
        "systemMessage": (
            "CONTEXT COMPACTION TRIGGERED. "
            "Re-read the current Linear issue state before proceeding. "
            "Do not assume previously-read data is still accurate."
        )
    }


async def enforce_list_filters(
    input_data: _HookInput, tool_use_id: str | None, context: HookContext
) -> AsyncHookJSONOutput | SyncHookJSONOutput:
    """PreToolUse: block mcp__linear__list_issues without teamId or projectId.

    Prevents Pitfall 4 (context overflow on unfiltered list). The hook returns
    a deny decision, forcing the agent to add a filter and retry.
    """
    raw: dict[str, Any] = cast("dict[str, Any]", input_data)
    if raw.get("tool_name") != "mcp__linear__list_issues":
        return {}
    tool_input: dict[str, Any] = raw.get("tool_input", {})
    if not tool_input.get("teamId") and not tool_input.get("projectId"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "list_issues requires teamId or projectId filter to prevent "
                    "context overflow. Add a filter and retry."
                ),
            }
        }
    return {}


# Hook bundle wired into ClaudeAgentOptions(hooks=...)
LINEAR_HOOKS: dict[HookEvent, list[HookMatcher]] = {
    "PostToolUseFailure": [
        HookMatcher(matcher="^mcp__linear__", hooks=[linear_retry_hook])
    ],
    "PostToolUse": [HookMatcher(matcher="^mcp__linear__", hooks=[linear_audit_hook])],
    "PreCompact": [HookMatcher(hooks=[pre_compact_handler])],
    "PreToolUse": [
        HookMatcher(matcher="mcp__linear__list_issues", hooks=[enforce_list_filters])
    ],
}
