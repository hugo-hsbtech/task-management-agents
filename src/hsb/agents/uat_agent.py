"""UAT Agent — standalone PydanticAI session validating User Stories
against acceptance criteria.

Scope structural enforcement:
- ``tools=[read_file, glob_files, grep_files]`` — read-only filesystem tools.
- No MCP servers — User Story JSON is in the prompt; cannot write to Linear.
- This module does NOT import ``hsb.agents.linear_agent``.
- :func:`run_uat_and_validate` does NOT modify Linear state — Plan 05-04
  is responsible for routing fix subtasks through the Linear Agent path.

G1 (PydanticAI requires ANTHROPIC_API_KEY) is checked at the chokepoint
:func:`hsb.agents.guards.assert_api_key_set`.

G3 backstop: :func:`hsb.agents.guards.assert_no_task_dispatch` is a noop
shim in PydanticAI (no Task tool exists) — preserved for source-grep tests.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.filesystem_tools import glob_files, grep_files, read_file
from hsb.agents.guards import assert_no_task_dispatch
from hsb.contracts.uat import UATResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def load_skill(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


_uat_agent: Agent[None, UATResult] = Agent(
    model=AnthropicModel("claude-sonnet-4-6"),
    output_type=UATResult,
    system_prompt="",  # Set dynamically in run_uat_and_validate
    tools=[read_file, glob_files, grep_files],
    output_retries=MAX_RETRIES,
)


async def run_uat_and_validate(
    user_story_id: str,
    acceptance_criteria: list[str],
    uat_cycle: int,
) -> UATResult:
    """Standalone PydanticAI session. Skill 08 inline.

    UATA-04: tools are read-only (read_file, glob_files, grep_files) — no
    Write/Edit/Agent tools registered.
    UATA-04: no MCP servers — User Story JSON is in the prompt.

    Returns validated :class:`UATResult`. PydanticAI's output_retries=3
    handles validation failures natively. Raises if all retries exhausted.

    WORC-02: ``"Agent"`` is absent from tools — no sub-subagent dispatch.
    """
    skill_08 = load_skill(".claude/skills/uat-validation/SKILL.md")
    scope_block = "\n".join(
        f"[AC-{i + 1}] {c}" for i, c in enumerate(acceptance_criteria)
    )

    prompt = (
        f"Validate User Story {user_story_id} (UAT cycle {uat_cycle}).\n\n"
        "SCOPE BOUNDARY: Only validate the acceptance criteria listed below. "
        "Do not evaluate any feature, behavior, or quality dimension not "
        "explicitly listed. Any finding that lacks a direct reference to a "
        "listed [AC-N] criterion is out of scope and must not appear in your "
        "response.\n\n"
        f"Acceptance criteria:\n{scope_block}\n\n"
        "Return a UATResult object."
    )

    # G3 shim (noop) — kept for source-grep compatibility
    assert_no_task_dispatch(None)

    # Build agent with skill_08 system prompt for this run
    skill_agent: Agent[None, UATResult] = Agent(
        model=AnthropicModel("claude-sonnet-4-6"),
        output_type=UATResult,
        system_prompt=skill_08,
        tools=[read_file, glob_files, grep_files],
        output_retries=MAX_RETRIES,
    )

    result = await skill_agent.run(
        prompt,
        usage_limits=UsageLimits(request_limit=20),
    )

    # Inject required fields from caller context
    output = result.output
    if not getattr(output, "user_story_id", None):
        output_dict = output.model_dump()
        output_dict["user_story_id"] = user_story_id
        output_dict["uat_cycle"] = uat_cycle
        output = UATResult(**output_dict)

    return output
