"""Backlog Agent — reads plan.md and creates Linear EPIC -> Story -> Task hierarchy.

Two-layer capability boundary (Pitfall 1 mitigation):
  Layer 1: .claude/skills/backlog-planning/SKILL.md frontmatter allowed-tools
  Layer 2: PydanticAI Agent.tools below

Both layers MUST list the same 4 tools (read_file + Linear MCP read/create)
and explicitly forbid Linear update/delete, Bash, Edit, Write. The IDEMPOTENCY
RULE in BACKLOG_SYSTEM_PROMPT enforces the list_issues pre-flight before any
create_issue call (Pitfall 1, BKPK-05).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.filesystem_tools import read_file
from hsb.agents.linear_middleware import make_linear_mcp_toolset
from hsb.contracts.backlog import BacklogInput, BacklogOutput

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

BACKLOG_SYSTEM_PROMPT = (
    "You are the Backlog Planning Agent for HSBTech. Your task: "
    "1. Read the plan.md content provided in the user prompt (free-form markdown). "
    "2. Parse it using language understanding — no required structure. "
    "3. Generate a structured EPIC -> User Story -> Task hierarchy. "
    "4. For every EPIC, User Story, and Task, embed the relevant plan.md excerpt in "
    "   the description field as a markdown blockquote (traceability per BKPK-05, D-03). "
    "\n\n"
    "IDEMPOTENCY RULE (BKPK-05, Pitfall 1): "
    "Before creating any EPIC, call mcp__linear__list_issues with the team filter and "
    "search for an existing EPIC with the same title. If one exists, use its existing ID "
    "and skip creation. NEVER create duplicate EPICs. "
    "\n\n"
    "FILTER REQUIREMENT (Pitfall): "
    "NEVER call mcp__linear__list_issues without a teamId or projectId filter — "
    "unfiltered list calls return the entire workspace and exhaust the context budget. "
    "\n\n"
    "RETRY ON FAILURE: If a Linear tool call fails, retry up to 3 times with "
    "exponential backoff (wait 1s, 2s, 4s between attempts). "
    "\n\n"
    "EPIC titles MUST start with '[EPIC] '. User Story titles SHOULD describe the user "
    "value. Task titles MUST be specific enough to estimate. "
    "\n\n"
    "OUTPUT FORMAT: Return a BacklogOutput object."
)

_backlog_agent: Agent[None, BacklogOutput] = Agent(
    model=AnthropicModel("claude-opus-4-7"),
    output_type=BacklogOutput,
    system_prompt=BACKLOG_SYSTEM_PROMPT,
    tools=[read_file],
    toolsets=[make_linear_mcp_toolset()],
    output_retries=MAX_VALIDATION_RETRIES,
)


async def _run_backlog_agent_async(input: BacklogInput) -> BacklogOutput:
    """Async core: PydanticAI Agent run with structured output."""
    plan_content = Path(input.plan_source).read_text()
    prompt = (
        f"Execute backlog planning. Project context:\n```json\n"
        f"{input.project_context.model_dump_json(indent=2)}\n```\n\n"
        f"plan.md content (path: {input.plan_source}):\n```markdown\n"
        f"{plan_content}\n```\n\n"
        f"Return a BacklogOutput object."
    )

    result = await _backlog_agent.run(
        prompt,
        usage_limits=UsageLimits(request_limit=80),
    )
    return result.output


def run_backlog_agent(input: BacklogInput) -> BacklogOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_backlog_agent_async(input))
