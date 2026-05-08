"""Backlog Agent — reads plan.md and creates Linear EPIC -> Story -> Task hierarchy.

Two-layer capability boundary (Pitfall 1 mitigation):
  Layer 1: .claude/skills/backlog-planning/SKILL.md frontmatter allowed-tools
  Layer 2: ClaudeAgentOptions.allowed_tools below

Both layers MUST list the same 4 tools (create_issue, list_issues, get_issue, Read)
and explicitly forbid Linear update/delete, Bash, Edit, Write. The IDEMPOTENCY
RULE in BACKLOG_SYSTEM_PROMPT enforces the list_issues pre-flight before any
create_issue call (Pitfall 1, BKPK-05).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.agents.hooks import LINEAR_HOOKS
from hsb.contracts.backlog import BacklogInput, BacklogOutput

load_dotenv()  # Loads ANTHROPIC_API_KEY from .env
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
    "EPIC titles MUST start with '[EPIC] '. User Story titles SHOULD describe the user "
    "value. Task titles MUST be specific enough to estimate. "
    "\n\n"
    "OUTPUT FORMAT: Emit a single JSON object as your final result, matching this schema "
    "exactly: { 'epics': [...], 'traceability': { 'plan_source': '<path>' } }. "
    "Emit ONLY the JSON object — no prose around it."
)


async def _run_backlog_agent_async(input: BacklogInput) -> BacklogOutput:
    """Async core: query loop + validation/retry. Synchronous wrapper below."""
    plan_content = Path(input.plan_source).read_text()
    base_prompt = (
        f"Execute backlog planning. Project context:\n```json\n"
        f"{input.project_context.model_dump_json(indent=2)}\n```\n\n"
        f"plan.md content (path: {input.plan_source}):\n```markdown\n"
        f"{plan_content}\n```\n\n"
        f"Return ONLY a JSON object matching BacklogOutput schema."
    )

    options = ClaudeAgentOptions(
        model="claude-opus-4-7",
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            }
        },
        allowed_tools=[
            "mcp__linear__create_issue",
            "mcp__linear__list_issues",
            "mcp__linear__get_issue",
            "Read",
        ],
        permission_mode="acceptEdits",
        system_prompt=BACKLOG_SYSTEM_PROMPT,
        max_turns=80,  # supports 20+ Linear creates
        hooks=LINEAR_HOOKS,
    )

    last_error: Exception | None = None
    prompt = base_prompt
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text: str | None = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                failed = [
                    s
                    for s in message.data.get("mcp_servers", [])
                    if s.get("status") != "connected"
                ]
                if failed:
                    raise RuntimeError(f"Linear MCP failed to connect: {failed}")
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
                    raise RuntimeError(f"Backlog Agent failed: {message.subtype}")

        if result_text is None:
            logger.warning("Attempt %d: no result text", attempt)
            continue
        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
            output = BacklogOutput.model_validate(raw)
            logger.info("Backlog Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            prompt = base_prompt + (
                f"\n\nPrevious attempt produced invalid output:\n{e}\n"
                "Return corrected JSON ONLY."
            )

    raise ValueError(
        f"Backlog Agent failed validation after {MAX_VALIDATION_RETRIES} attempts: {last_error}"
    )


def run_backlog_agent(input: BacklogInput) -> BacklogOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_backlog_agent_async(input))
