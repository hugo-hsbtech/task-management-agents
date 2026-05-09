"""Git Agent — branches, PRs, REBASE_STACK via gh CLI + git only.

GITA-05: No Edit/Write, no Linear MCP, no merge to main.
Two-layer enforcement (SKILL.md + this file).
--force-with-lease ONLY (no bare --force, Pitfall 3).
--limit 100 on gh pr list (Pitfall 4).
"""
from __future__ import annotations

import asyncio
import logging

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.subprocess_tools import (
    gh_pr_create,
    gh_pr_diff,
    gh_pr_list,
    gh_pr_view,
    git_add,
    git_checkout,
    git_commit,
    git_fetch,
    git_log,
    git_push_force_with_lease,
    git_rebase,
    git_status,
)
from hsb.contracts.git import GitInput, GitOutput

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
    "sibling task PRs targeting the EPIC branch via gh_pr_list with base=<epic-branch>. "
    "CRITICAL: --limit 100 is built into gh_pr_list to prevent pagination truncation (Pitfall 4). "
    "For each sibling (excluding the just-merged): git_fetch; git_checkout(branch); "
    "git_rebase(onto=<epic-branch>, old_tip=<old>, branch=<branch>); "
    "git_push_force_with_lease(branch). "
    "CRITICAL: only git_push_force_with_lease is available (NOT bare --force) — "
    "prevents overwriting concurrent pushes (Pitfall 3). "
    "\n\nCAPABILITY BOUNDARY (GITA-05): You MUST NOT: "
    "- Run any merge command (no gh pr merge, no git merge). "
    "- Edit or Write any source files. "
    "- Call any Linear MCP tool (you have none). "
    "\n\nOUTPUT FORMAT: Return a GitOutput object. The schema FORBIDS extra fields."
)

_git_agent: Agent[None, GitOutput] = Agent(
    model=AnthropicModel("claude-sonnet-4-6"),
    output_type=GitOutput,
    system_prompt=GIT_SYSTEM_PROMPT,
    tools=[
        git_checkout,
        git_push_force_with_lease,
        git_rebase,
        git_fetch,
        git_log,
        git_status,
        git_add,
        git_commit,
        gh_pr_create,
        gh_pr_list,
        gh_pr_view,
        gh_pr_diff,
    ],
    output_retries=MAX_VALIDATION_RETRIES,
)


async def _run_git_agent_async(input: GitInput) -> GitOutput:
    prompt = (
        f"Execute git/PR operations for this Builder output:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Return a GitOutput object."
    )

    result = await _git_agent.run(
        prompt,
        usage_limits=UsageLimits(request_limit=30),
    )
    return result.output


def run_git_agent(input: GitInput) -> GitOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_git_agent_async(input))
