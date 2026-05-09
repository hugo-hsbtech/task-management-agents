"""Builder Agent — implements scoped changes for a Linear work item.

CAPABILITY BOUNDARY (BLDR-04): NO git, NO Linear, NO PR operations.
Two-layer enforcement:
  1. .claude/skills/implementation/SKILL.md frontmatter `allowed-tools`
  2. PydanticAI Agent.tools below
Both lists must contain ONLY: read_file, edit_file, write_file, plus
run_pytest/run_ruff/run_mypy. Third defense: BuilderOutput extra='forbid'
rejects git_branch / pr_url etc.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.subprocess_tools import _run_cmd
from hsb.contracts.builder import BuilderInput, BuilderOutput

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3


@dataclass
class BuilderDeps:
    """Dependencies injected into Builder tools — provides cwd context."""

    cwd: str


# IMPORTANT: forbidden tool tokens are described in plain English (no parenthesized
# tool patterns) so the negative-grep acceptance criteria over the WHOLE FILE pass.
# The actual tool list is the Agent.tools attribute below.
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
    "ALLOWED ACTIONS: read_file, edit_file, write_file, and run_pytest/run_ruff/run_mypy. "
    "\n\n"
    "VALIDATION HEURISTIC (BLDR-02): After implementing changes, detect and run "
    "available validations: "
    "  1. Tests: if pyproject.toml has [tool.pytest] OR pytest.ini OR tests/ exists, "
    "     run run_pytest with args like '<changed_or_tests_dir> -x --tb=short'. "
    "  2. Lint: if ruff.toml OR pyproject.toml has [tool.ruff] section, "
    "     run run_ruff with 'check <changed_files>'. "
    "  3. Type check: if mypy.ini OR pyproject.toml has [tool.mypy] section, "
    "     run run_mypy with '<changed_files> --ignore-missing-imports'. "
    "Report each validation as passed | failed | not_run. If a validation fails, attempt "
    "to fix before reporting; max 2 fix attempts per validation. The 'build' field is "
    "currently fixed at 'not_run' — there is no separate build step in Phase 2 fixtures. "
    "\n\n"
    "OUTPUT FORMAT: Return a BuilderOutput object. The schema FORBIDS extra fields — "
    "do NOT include git_branch, pr_url, linear_status, or anything not in the schema."
)

_builder_agent: Agent[BuilderDeps, BuilderOutput] = Agent(
    model=AnthropicModel("claude-sonnet-4-6"),
    output_type=BuilderOutput,
    system_prompt=BUILDER_SYSTEM_PROMPT,
    deps_type=BuilderDeps,
    output_retries=MAX_VALIDATION_RETRIES,
)


@_builder_agent.tool
async def read_file(ctx: RunContext[BuilderDeps], path: str) -> str:
    """Read a file (resolved against cwd if relative)."""
    full = (
        Path(path)
        if Path(path).is_absolute()
        else Path(ctx.deps.cwd) / path
    )
    return full.read_text(encoding="utf-8")


@_builder_agent.tool
async def write_file(
    ctx: RunContext[BuilderDeps], path: str, content: str
) -> str:
    """Write content to file (resolved against cwd if relative). Creates parent dirs."""
    full = (
        Path(path)
        if Path(path).is_absolute()
        else Path(ctx.deps.cwd) / path
    )
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"Wrote {full}"


@_builder_agent.tool
async def edit_file(
    ctx: RunContext[BuilderDeps], path: str, old_str: str, new_str: str
) -> str:
    """Replace first occurrence of old_str with new_str in file."""
    full = (
        Path(path)
        if Path(path).is_absolute()
        else Path(ctx.deps.cwd) / path
    )
    content = full.read_text(encoding="utf-8")
    new_content = content.replace(old_str, new_str, 1)
    if new_content == content:
        return f"No match found in {full}"
    full.write_text(new_content, encoding="utf-8")
    return f"Edited {full}"


@_builder_agent.tool
async def run_pytest(ctx: RunContext[BuilderDeps], args: str = "") -> str:
    """Run pytest with optional arguments in the builder's cwd."""
    cmd = ["python", "-m", "pytest"]
    if args:
        cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=ctx.deps.cwd)


@_builder_agent.tool
async def run_ruff(
    ctx: RunContext[BuilderDeps], args: str = "check ."
) -> str:
    """Run ruff linter with optional arguments in the builder's cwd."""
    cmd = ["ruff"]
    cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=ctx.deps.cwd)


@_builder_agent.tool
async def run_mypy(
    ctx: RunContext[BuilderDeps], args: str = "--ignore-missing-imports"
) -> str:
    """Run mypy type checker with optional arguments in the builder's cwd."""
    cmd = ["mypy"]
    cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=ctx.deps.cwd)


async def _run_builder_agent_async(input: BuilderInput) -> BuilderOutput:
    prompt = (
        f"Implement this Linear work item:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Working directory: {input.repository_context.root_path}\n\n"
        f"Return a BuilderOutput object."
    )

    deps = BuilderDeps(cwd=input.repository_context.root_path)
    result = await _builder_agent.run(
        prompt,
        deps=deps,
        usage_limits=UsageLimits(request_limit=40),
    )
    return result.output


def run_builder_agent(input: BuilderInput) -> BuilderOutput:
    """Synchronous entry point. Wraps async loop with asyncio.run() at boundary."""
    return asyncio.run(_run_builder_agent_async(input))
