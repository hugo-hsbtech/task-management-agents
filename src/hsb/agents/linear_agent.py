"""Linear Agent — wraps mcp__linear__* tools behind a pydantic-validated contract.

Two public entry points:
  - run_linear_agent(prompt): one-shot agent run, returns LinearOutput
  - run_validated_linear_agent(operation, payload): wraps run_linear_agent,
    routes WRITEs through G5 stack-inspection guard.

PydanticAI's output_type=LinearOutput eliminates the manual JSON-parse retry
loop — output_retries=3 handles validation failures natively.

Per D-01: OAuth handled by mcp-remote. Per D-02: token refresh automatic.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.guards import linear_write_guard
from hsb.agents.linear_middleware import make_linear_mcp_toolset
from hsb.contracts.linear import LinearOutput

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
    "On tool failure, retry up to 3 times with exponential backoff (1s, 2s, 4s). "
    "For every write operation (create_issue, update_issue, create_comment): "
    "  1. Read the entity first via mcp__linear__get_issue and capture its updatedAt timestamp. "
    "  2. Perform the write. "
    "  3. Re-read the entity via mcp__linear__get_issue and capture the new updatedAt. "
    "  4. Verify post_updatedAt > pre_updatedAt (optimistic lock). "
    "Never call mcp__linear__list_issues without a teamId or projectId filter. "
    "Always set parentId at create time — never reparent a Linear issue after creation. "
    "Return your final result as a single JSON object matching the LinearOutput schema."
)

_linear_agent: Agent[None, LinearOutput] = Agent(
    model=AnthropicModel("claude-sonnet-4-6"),
    output_type=LinearOutput,
    system_prompt=LINEAR_SYSTEM_PROMPT,
    toolsets=[make_linear_mcp_toolset()],
    output_retries=MAX_VALIDATION_RETRIES,
)


async def run_linear_agent(prompt: str) -> LinearOutput:
    """Execute one Linear Agent turn. Returns validated LinearOutput.

    PydanticAI handles the message loop, MCP connection, and JSON validation
    natively. output_type=LinearOutput + output_retries=3 replaces the
    manual JSON-parse retry loop.
    """
    result = await _linear_agent.run(
        prompt,
        usage_limits=UsageLimits(request_limit=20),
    )
    return result.output


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
        "Return your result as a JSON object matching the LinearOutput schema."
    )
    return await run_linear_agent(prompt)


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
    and call the implementation directly.
    """
    if operation in _WRITE_OPERATIONS:
        result: LinearOutput = await _run_validated_linear_agent_write(operation, payload)
        return result
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
