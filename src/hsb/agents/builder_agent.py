"""Builder Agent — implements scoped changes for a Linear work item.

CAPABILITY BOUNDARY (BLDR-04): NO git, NO Linear, NO PR operations.
Two-layer enforcement:
  1. .claude/skills/implementation/SKILL.md frontmatter `allowed-tools`
  2. ClaudeAgentOptions.allowed_tools below
Both lists must contain ONLY: Read, Edit, Write, plus pytest/ruff/mypy/python
bash subcommand patterns. Third defense: BuilderOutput extra='forbid' rejects
git_branch / pr_url etc.
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

from hsb.contracts.builder import BuilderInput, BuilderOutput

load_dotenv()
logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

# IMPORTANT: forbidden tool tokens are described in plain English (no parenthesized
# tool patterns) so the negative-grep acceptance criteria over the WHOLE FILE pass.
# The actual allow-list is the ClaudeAgentOptions.allowed_tools attribute below.
BUILDER_SYSTEM_PROMPT = (
    "You are the Builder Agent for HSBTech. Implement ONLY the scoped change described "
    "in the Linear work item provided in the user prompt. "
    "\n\n"
    "CAPABILITY BOUNDARY (BLDR-04): You MUST NOT: "
    "  - Create or checkout git branches "
    "  - Run git commit or git push "
    "  - Run gh CLI commands "
    "  - Call any Linear MCP tool (you have none) "
    "  - Write to Linear in any way "
    "  - Modify files outside the work item scope "
    "\n\n"
    "ALLOWED ACTIONS: Read, Edit, Write, and Bash for pytest/ruff/mypy/python only. "
    "\n\n"
    "VALIDATION HEURISTIC (BLDR-02): After implementing changes, detect and run "
    "available validations: "
    "  1. Tests: if pyproject.toml has [tool.pytest] OR pytest.ini OR tests/ exists, "
    "     run `pytest <changed_or_tests_dir> -x --tb=short`. "
    "  2. Lint: if ruff.toml OR pyproject.toml has [tool.ruff] section, "
    "     run `ruff check <changed_files>`. "
    "  3. Type check: if mypy.ini OR pyproject.toml has [tool.mypy] section, "
    "     run `mypy <changed_files> --ignore-missing-imports`. "
    "Report each validation as passed | failed | not_run. If a validation fails, attempt "
    "to fix before reporting; max 2 fix attempts per validation. The 'build' field is "
    "currently fixed at 'not_run' — there is no separate build step in Phase 2 fixtures. "
    "\n\n"
    "OUTPUT FORMAT: Emit a single JSON object as your final result, matching BuilderOutput "
    "schema. The schema FORBIDS extra fields — do NOT include git_branch, pr_url, "
    "linear_status, or anything not in the schema. Emit ONLY the JSON object — no prose."
)


async def _run_builder_agent_async(input: BuilderInput) -> BuilderOutput:
    base_prompt = (
        f"Implement this Linear work item:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Working directory: {input.repository_context.root_path}\n\n"
        f"Return ONLY a JSON object matching BuilderOutput schema."
    )

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        allowed_tools=[
            "Read",
            "Edit",
            "Write",
            "Bash(pytest *)",
            "Bash(ruff *)",
            "Bash(mypy *)",
            "Bash(python *)",
        ],
        # NO mcp_servers entry — Builder has zero MCP access
        permission_mode="acceptEdits",
        system_prompt=BUILDER_SYSTEM_PROMPT,
        max_turns=40,
        cwd=input.repository_context.root_path,
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
                    raise RuntimeError(f"Builder Agent failed: {message.subtype}")

        if result_text is None:
            logger.warning("Attempt %d: no result text", attempt)
            continue
        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
            output = BuilderOutput.model_validate(raw)
            logger.info("Builder Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            prompt = base_prompt + (
                f"\n\nPrevious attempt produced invalid output:\n{e}\n"
                "Return corrected JSON ONLY. Reminder: schema forbids extra fields "
                "(no git_branch, no pr_url)."
            )

    raise ValueError(
        f"Builder Agent failed validation after {MAX_VALIDATION_RETRIES} attempts: {last_error}"
    )


def run_builder_agent(input: BuilderInput) -> BuilderOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_builder_agent_async(input))
