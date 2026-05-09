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

from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.agents._sdk_options import make_agent_options, resolve_runtime

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

    options = make_agent_options(
        system_prompt=BACKLOG_SYSTEM_PROMPT,
        allowed_tools=[
            "mcp__linear__create_issue",
            "mcp__linear__list_issues",
            "mcp__linear__get_issue",
            "Read",
        ],
        permission_mode="acceptEdits",
        max_turns=80,  # supports 20+ Linear creates
        model="claude-opus-4-7",
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            }
        },
        hooks=LINEAR_HOOKS,
    )
    runtime = resolve_runtime("backlog")

    last_error: Exception | None = None
    prompt = base_prompt
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text: str | None = None
        async for message in runtime.query(prompt, options):
            sdk_msg = message.raw

            # Claude-only: SystemMessage init exposes per-MCP connection status.
            # Codex MCP failures surface earlier via verify_codex_mcp() at query
            # entry, so this path is intentionally Claude-only.
            if isinstance(sdk_msg, SystemMessage) and sdk_msg.subtype == "init":
                failed = [
                    s
                    for s in sdk_msg.data.get("mcp_servers", [])
                    if s.get("status") != "connected"
                ]
                if failed:
                    raise RuntimeError(f"Linear MCP failed to connect: {failed}")
                continue

            # Claude AssistantMessage: print text + tool-use names for observability.
            if isinstance(sdk_msg, AssistantMessage):
                for block in sdk_msg.content:
                    if hasattr(block, "text"):
                        print(block.text)
                    elif hasattr(block, "name"):
                        print(f"[TOOL] {block.name}")
                continue

            # Claude ResultMessage: explicit success/failure subtype.
            if isinstance(sdk_msg, ResultMessage):
                if sdk_msg.subtype == "success":
                    result_text = sdk_msg.result
                else:
                    raise RuntimeError(f"Backlog Agent failed: {sdk_msg.subtype}")
                continue

            # Runtime-agnostic path (covers Codex events): accumulate text from
            # any Message that carries content, and treat is_final as the final
            # result sentinel. This is what makes the agent flip-able.
            if message.text:
                print(message.text)
            if message.is_final:
                # On Codex, the final event carries the model's last message
                # text in message.text. On Claude this branch is unreachable
                # (ResultMessage handler above sets result_text and continues).
                if result_text is None:
                    result_text = message.text

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
