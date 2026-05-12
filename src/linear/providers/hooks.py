"""Hook functions for Linear MCP tool calls.

All functions are plain async callables with no SDK dependency.
Claude-specific wiring lives in ``linear.providers.claude``.

Implements:
  - LINR-05 exponential backoff + audit log  (PostToolUseFailure / PostToolUse)
  - Pitfall 4 context-overflow prevention     (PreToolUse — enforce_list_filters)
  - Pitfall 6 transcript-loss prevention      (PreCompact — pre_compact_handler)
"""

import asyncio
import contextlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

import settings
from linear.prompts import CONTEXT_COMPACTION, RETRY_ATTEMPT, RETRY_EXHAUSTED


class ToolEventData(TypedDict, total=False):
    """Input shape for PostToolUse / PostToolUseFailure hook events."""

    tool_name: str
    tool_use_id: str | None
    tool_output: Any


class PreToolUseData(TypedDict, total=False):
    """Input shape for PreToolUse hook events."""

    tool_name: str
    tool_input: dict[str, Any]


class PreCompactData(TypedDict, total=False):
    """Input shape for PreCompact hook events."""

    transcript_path: str | None


_retry_counts: dict[str, int] = {}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0


async def linear_retry_hook(
    input_data: ToolEventData, tool_use_id: str | None, context: Any
) -> dict:
    """PostToolUseFailure: exponential backoff for mcp__linear__* failures."""
    tool_name = input_data.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}

    key = tool_use_id or tool_name
    retry_count = _retry_counts.get(key, 0)

    if retry_count >= MAX_RETRIES:
        _retry_counts.pop(key, None)
        return {
            "systemMessage": RETRY_EXHAUSTED.format(
                tool_name=tool_name, max_retries=MAX_RETRIES
            )
        }

    delay = BASE_DELAY_SECONDS * (2**retry_count)
    _retry_counts[key] = retry_count + 1
    await asyncio.sleep(delay)

    return {
        "systemMessage": RETRY_ATTEMPT.format(
            tool_name=tool_name,
            attempt=retry_count + 1,
            max_retries=MAX_RETRIES,
            delay=delay,
        )
    }


async def linear_audit_hook(
    input_data: ToolEventData, tool_use_id: str | None, context: Any
) -> dict:
    """PostToolUse: append a JSON line to the configured audit log per Linear call."""
    tool_name = input_data.get("tool_name", "")
    if not tool_name.startswith("mcp__linear__"):
        return {}

    if tool_use_id:
        _retry_counts.pop(tool_use_id, None)

    audit_log = settings.linear.audit_log_path
    Path(audit_log).parent.mkdir(parents=True, exist_ok=True)

    output = input_data.get("tool_output", {})
    output_repr = (
        json.dumps(output)[:2000] if not isinstance(output, str) else output[:2000]
    )

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool_name,
        "tool_use_id": tool_use_id,
        "tool_output_preview": output_repr,
    }
    with open(audit_log, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return {}


async def pre_compact_handler(
    input_data: PreCompactData, tool_use_id: str | None, context: Any
) -> dict:
    """PreCompact: archive transcript and instruct agent to re-read Linear state."""

    transcript_path = input_data.get("transcript_path")
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    archive_path = f"{settings.linear.compaction_archive_dir}/compaction_{ts}.jsonl"
    if transcript_path:
        with contextlib.suppress(FileNotFoundError, PermissionError):
            shutil.copy(transcript_path, archive_path)
    return {"systemMessage": CONTEXT_COMPACTION}


async def enforce_list_filters(
    input_data: PreToolUseData, tool_use_id: str | None, context: Any
) -> dict:
    """PreToolUse: deny mcp__linear__list_issues without teamId or projectId."""
    if input_data.get("tool_name") != "mcp__linear__list_issues":
        return {}

    tool_input = input_data.get("tool_input", {})
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
