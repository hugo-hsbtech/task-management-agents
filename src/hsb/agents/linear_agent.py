"""Linear Agent — wraps mcp__linear__* tools behind a pydantic-validated contract.

Two public entry points:
  - run_linear_agent(prompt): raw async query loop, returns ResultMessage.result text
  - run_validated_linear_agent(operation, payload): wraps run_linear_agent, validates
    against LinearOutput, retries up to MAX_VALIDATION_RETRIES on validation failure.

Per D-01: OAuth handled by mcp-remote. Per D-02: token refresh automatic.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, cast

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.agents._sdk_options import linear_write_guard
from hsb.agents.hooks import LINEAR_HOOKS
from hsb.contracts.linear import LinearOutput

load_dotenv()  # Loads ANTHROPIC_API_KEY from .env

# Phase 5 G5 (RISK-04 layer 4): write operations dispatched through
# run_validated_linear_agent are routed through a guarded inner shim that
# inspects the call stack for frames originating in risk_agent.py outside
# the operator-delegated approve_improvement_trigger path. READ operations
# bypass the guard.
_WRITE_OPERATIONS = {
    "create",
    "update",
    "create_comment",
    "create_subtasks",
    "create_issue",
    "update_issue",
}

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

LINEAR_SYSTEM_PROMPT = (
    "You are the Linear Agent for the HSBTech AI Engineering Workflow. "
    "You manage Linear work items via the mcp__linear__* tools. "
    "You MUST validate all inputs against the contract schema before calling tools. "
    "On tool failure, retry up to 3 times with exponential backoff (1s, 2s, 4s) — "
    "the SDK retry hook handles timing automatically; just retry the same tool call when instructed. "
    "For every write operation (create_issue, update_issue, create_comment): "
    "  1. Read the entity first via mcp__linear__get_issue and capture its updatedAt timestamp. "
    "  2. Perform the write. "
    "  3. Re-read the entity via mcp__linear__get_issue and capture the new updatedAt. "
    "  4. Verify post_updatedAt > pre_updatedAt (optimistic lock). "
    "Never call mcp__linear__list_issues without a teamId or projectId filter. "
    "Always set parentId at create time — never reparent a Linear issue after creation. "
    "Return your final result as a single JSON object matching this schema exactly: "
    '{ "operation": <op>, "result": "success"|"failed", '
    '"linear_entities": [{ "id": "LIN-...", "type": "epic|user_story|task|subtask", '
    '"url": "https://linear.app/..." }], "error": <string or null> }. '
    "Do not include any prose around the JSON — emit ONLY the JSON object as the final result."
)


async def run_linear_agent(prompt: str) -> str | None:
    """Execute one Linear Agent turn. Returns the result string or None on failure.

    The async generator from query() yields SystemMessage, AssistantMessage,
    and ResultMessage objects. We:
      - verify MCP server connectivity at SystemMessage(subtype='init')
      - stream assistant text and tool calls to stdout for operator visibility
      - capture the final ResultMessage.result string
    """
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            }
        },
        allowed_tools=["mcp__linear__*"],
        permission_mode="acceptEdits",
        system_prompt=LINEAR_SYSTEM_PROMPT,
        max_turns=20,
        hooks=LINEAR_HOOKS,
    )

    result_text: str | None = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            mcp_servers = message.data.get("mcp_servers", [])
            # Only inspect servers we registered — the SDK init message may
            # surface globally-registered MCPs (e.g. user-level OAuth servers)
            # whose auth state is unrelated to this agent.
            required = {"linear"}
            failed = [
                s
                for s in mcp_servers
                if s.get("name") in required and s.get("status") != "connected"
            ]
            if failed:
                raise RuntimeError(f"Linear MCP server failed to connect: {failed}")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
                elif hasattr(block, "name"):
                    print(f"[TOOL] {block.name}")
        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                result_text = message.result
            else:
                raise RuntimeError(f"Agent failed: {message.subtype}")

    return result_text


async def _run_validated_linear_agent_impl(
    operation: str,
    payload: dict[str, Any],
) -> LinearOutput:
    """Internal implementation. Use :func:`run_validated_linear_agent` instead.

    The public function dispatches WRITE operations through
    :func:`_run_validated_linear_agent_write` (which carries the G5
    ``linear_write_guard`` decorator) so the call stack is inspected for
    Risk Agent frames before any Linear mutation runs.
    """
    prompt = (
        f"Execute Linear operation '{operation}' with this payload:\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        "Return your result as a JSON object matching this schema:\n"
        '{ "operation": "<op>", "result": "success"|"failed", '
        '"linear_entities": [...], "error": "<string or null>" }'
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text = await run_linear_agent(prompt)

        if result_text is None:
            logger.warning("Attempt %d: agent returned None result", attempt)
            continue

        # Extract JSON from result text (agent may wrap in markdown despite instructions)
        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "Attempt %d: could not parse JSON from result: %s", attempt, e
            )
            last_error = e
            prompt += (
                f"\n\nPrevious attempt returned invalid JSON: {e}. "
                "Return ONLY valid JSON, no prose around it."
            )
            continue

        try:
            output = LinearOutput.model_validate(raw)
            logger.info("Attempt %d: validation succeeded", attempt)
            return output
        except ValidationError as e:
            last_error = e
            logger.warning(
                "Attempt %d: LinearOutput validation failed:\n%s",
                attempt,
                e.json(indent=2),
            )
            prompt += (
                f"\n\nPrevious attempt returned invalid output. Validation errors:\n"
                f"{e.json(indent=2)}\nFix these errors and return corrected JSON."
            )

    raise ValueError(
        f"Linear Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# Phase 5 G5 (RISK-04 layer 4): wrap WRITE dispatch path with the
# linear_write_guard decorator. The decorator inspects the call stack and
# raises PermissionError if any frame originates from risk_agent.py outside
# the operator-delegated global_orchestrator.approve_improvement_trigger path.
@linear_write_guard
async def _run_validated_linear_agent_write(
    operation: str,
    payload: dict[str, Any],
) -> LinearOutput:
    """G5-guarded WRITE entry point. Delegates to the unguarded implementation
    after passing the stack-inspection check."""
    return await _run_validated_linear_agent_impl(operation, payload)


async def run_validated_linear_agent(
    operation: str,
    payload: dict[str, Any],
) -> LinearOutput:
    """Public Linear Agent entry point.

    WRITE operations (in :data:`_WRITE_OPERATIONS`) flow through the
    :func:`_run_validated_linear_agent_write` shim which carries the G5
    ``linear_write_guard`` decorator. READ operations bypass the guard
    and call the implementation directly. This preserves Phase 1's
    retry/validation logic untouched while adding the RISK-04 layer-4
    runtime defense.
    """
    if operation in _WRITE_OPERATIONS:
        # mypy can't resolve linear_write_guard's overloads across module
        # boundaries (it picks the impl signature `Any -> Any` instead of the
        # `Callable[P, Awaitable[R]] -> Callable[P, Awaitable[R]]` overload).
        # The decorator preserves the wrapped function's signature at runtime;
        # cast restores the type-checker's view of the awaited result, and the
        # no-untyped-call suppression covers the call itself.
        return cast(
            "LinearOutput",
            await _run_validated_linear_agent_write(operation, payload),  # type: ignore[no-untyped-call]
        )
    return await _run_validated_linear_agent_impl(operation, payload)


if __name__ == "__main__":
    # Smoke test: list teams (read-only). Requires ANTHROPIC_API_KEY in env and
    # a one-time interactive OAuth login for mcp-remote.
    result = asyncio.run(
        run_linear_agent(
            "List the available Linear teams. Return a JSON object: "
            '{"operation": "read", "result": "success", "linear_entities": [], "error": null}'
        )
    )
    print("\n--- RESULT ---")
    print(result)
