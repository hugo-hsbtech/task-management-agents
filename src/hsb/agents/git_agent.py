"""Git Agent — branches, PRs, REBASE_STACK via gh CLI + git only.

GITA-05: No Edit/Write, no Linear MCP, no merge to main.
Two-layer enforcement (SKILL.md + this file).
--force-with-lease ONLY (no bare --force, Pitfall 3).
--limit 100 on gh pr list (Pitfall 4).
"""

from __future__ import annotations

import asyncio
import json
import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.contracts.git import GitInput, GitOutput

load_dotenv()
logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

GIT_SYSTEM_PROMPT = (
    "You are the Git Agent for HSBTech. Create branches and PRs from completed Builder output. "
    "\n\nBRANCH NAMING (GITA-01): feature/LIN-{id}-{slug}. "
    "id is the integer from work_item_id; slug is lowercase hyphen-separated, max 50 chars. "
    "\n\nPR TITLE (GITA-03): [LIN-{id}] {short description}. "
    "\n\nPR BASE (D-07): All task PRs target the EPIC branch directly. "
    "epic_id from input determines the base: epic/LIN-{number}. "
    "NEVER target main directly. NEVER target another task branch. "
    "\n\nREBASE_STACK (GITA-04, D-08): When a sibling task PR is merged, enumerate ALL open "
    "sibling task PRs targeting the EPIC branch via: "
    "gh pr list --base <epic-branch> --state open --limit 100 --json number,headRefName "
    "CRITICAL: --limit 100 prevents pagination truncation (Pitfall 4). "
    "For each sibling (excluding the just-merged): git fetch origin; git checkout <branch>; "
    "git rebase --onto <epic-branch> <old-tip> <branch>; "
    "git push --force-with-lease origin <branch> "
    "CRITICAL: --force-with-lease (NOT bare --force) — prevents overwriting concurrent pushes (Pitfall 3). "
    "\n\nCAPABILITY BOUNDARY (GITA-05): You MUST NOT: "
    "- Run any merge command (no gh pr merge, no git merge). "
    "- Run git push without --force-with-lease (use --force-with-lease only). "
    "- Edit or Write any source files. "
    "- Call any Linear MCP tool (you have none). "
    "\n\nOUTPUT FORMAT: Emit a single JSON object matching GitOutput schema. The schema "
    "FORBIDS extra fields — do NOT include merged_to_main, linear_status, or anything not in "
    "the schema. Emit ONLY the JSON object."
)


async def _run_git_agent_async(input: GitInput) -> GitOutput:
    base_prompt = (
        f"Execute git/PR operations for this Builder output:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Return ONLY a JSON object matching GitOutput schema."
    )
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        allowed_tools=[
            "Bash(gh pr create *)",
            "Bash(gh pr list *)",
            "Bash(gh pr view *)",
            "Bash(gh pr diff *)",
            "Bash(git checkout *)",
            "Bash(git push --force-with-lease *)",
            "Bash(git rebase *)",
            "Bash(git log *)",
            "Bash(git fetch *)",
            "Bash(git add *)",
            "Bash(git commit *)",
            "Bash(git status *)",
        ],
        permission_mode="acceptEdits",
        system_prompt=GIT_SYSTEM_PROMPT,
        max_turns=30,
    )

    last_error: Exception | None = None
    prompt = base_prompt
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text: str | None = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        print(block.text)
                    elif hasattr(block, "name"):
                        print(f"[TOOL] {block.name}")
            elif isinstance(message, ResultMessage):
                if message.subtype == "success":
                    result_text = message.result
                else:
                    raise RuntimeError(f"Git Agent failed: {message.subtype}")
        if result_text is None:
            logger.warning("Attempt %d: no result text", attempt)
            continue
        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
            output = GitOutput.model_validate(raw)
            logger.info("Git Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            prompt = base_prompt + (
                f"\n\nPrevious attempt produced invalid output:\n{e}\n"
                "Return corrected JSON ONLY. Schema forbids extra fields."
            )

    raise ValueError(
        f"Git Agent failed validation after {MAX_VALIDATION_RETRIES} attempts: {last_error}"
    )


def run_git_agent(input: GitInput) -> GitOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_git_agent_async(input))
