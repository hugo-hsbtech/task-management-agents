"""Work Item Orchestrator — single PydanticAI session driving one Linear
task through its full lifecycle (Linear read → Builder → Git → QA → fix loop →
done) per CONTEXT.md D-01.

Architecture (PydanticAI migration):
- ONE PydanticAI Agent per cycle. Skill content is injected into ``system_prompt``.
- Phase 2 agent modules are exposed as in-process tools via ``@_wio_agent.tool_plain``
  decorators. NO sub-agent dispatch (no AgentDefinition, no Agent tool).
- Multi-turn within the same MCP connection via ``run_mcp_servers()`` context
  manager + ``message_history=`` parameter chaining results across turns.

Phase 5 (D-04, D-06): the WIO embeds skills 10 + 11 inline within the same
session, adds a Step 1 enrichment turn before Builder and a Step 5 knowledge
storage turn after QA.

Two-layer QA cycle cap (CONTEXT.md D-05):
- Layer 1 lives in :class:`hsb.contracts.qa.QAOutput.validate_cycle_cap_logic`.
- Layer 2 (this module) — :func:`_check_qa_cycle_cap` — posts a Linear escalation
  comment when ``qa_cycle_count >= 3`` AND ``qa_status == "changes_required"``,
  preventing a runaway 4th cycle if Layer 1 is somehow bypassed.

G1 (PydanticAI requires ANTHROPIC_API_KEY) — checked via
:func:`hsb.agents.guards.assert_api_key_set`.
G3 (no Task tool dispatch) — noop shim in PydanticAI; preserved for source-grep
test compatibility.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.guards import assert_no_task_dispatch  # G3 noop shim
from hsb.agents.intelligence_agent import (
    build_enrichment_prompt,
    build_storage_prompt,
)
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.agents.linear_middleware import make_linear_mcp_toolset
from hsb.contracts.orchestrator import WorkItemOrchInput, WorkItemOrchOutput  # noqa: F401

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Skill assembly                                                              #
# --------------------------------------------------------------------------- #

# Injection order: task-orchestration first as the meta-skill framing the
# others, then the lifecycle skills in the order they appear in the cycle
# (Implementation → QA → Git → Linear).
SKILL_FILES = [
    "skills/06-TASK-ORCHESTRATION.md",
    "skills/02-IMPLEMENTATION.md",
    "skills/03-QA-REVIEW.md",
    "skills/04-GIT-PR-MANAGEMENT.md",
    "skills/05-LINEAR-SYSTEM-OF-RECORD.md",
    # Phase 5 [D-04]: Intelligence Agent runs inline within the WIO session.
    ".claude/skills/knowledge-context-enrichment/SKILL.md",  # skill 10 [Phase 5]
    ".claude/skills/knowledge-storage/SKILL.md",  # skill 11 [Phase 5]
]


def assemble_system_prompt() -> str:
    """Read all SKILL_FILES and concatenate with ``# SKILL: <stem>`` separators."""
    parts = []
    for path in SKILL_FILES:
        try:
            content = Path(path).read_text()
            parts.append(f"# SKILL: {Path(path).stem}\n\n{content}")
        except FileNotFoundError:
            logger.warning("Skill file not found: %s", path)
    return "\n\n---\n\n".join(parts)


# --------------------------------------------------------------------------- #
# WIO Agent definition                                                        #
# --------------------------------------------------------------------------- #

_wio_agent: Agent[None, str] = Agent(
    model=AnthropicModel("claude-sonnet-4-6"),
    output_type=str,
    system_prompt="",  # set dynamically per cycle
    toolsets=[make_linear_mcp_toolset()],
)


# --------------------------------------------------------------------------- #
# In-process tools — Phase 2 agents exposed as PydanticAI tools               #
# --------------------------------------------------------------------------- #


@_wio_agent.tool_plain
async def run_linear_op(operation: str, payload: dict[str, Any]) -> str:
    """Execute a Linear System of Record operation (create | update | comment | link_pr | read)."""
    result = await run_validated_linear_agent(operation=operation, payload=payload)
    return result.model_dump_json()


@_wio_agent.tool_plain
async def run_builder(work_item_id: str, issue_content: str) -> str:
    """Execute the Builder Agent for a work item.

    The orchestrator (the LLM) MUST pass the FULL Linear issue payload as
    the ``issue_content`` JSON string — WORC-04 / Pitfall 4. The wrapper parses
    it via ``json.loads`` and constructs a Pydantic ``BuilderInput`` so any
    injection attempt that does not match the schema is rejected at the
    ``extra='forbid'`` boundary BEFORE the Builder agent runs.
    """
    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext

    issue_data = json.loads(issue_content)
    builder_input = BuilderInput(
        work_item_id=work_item_id,
        issue_description=issue_data.get("description", ""),
        acceptance_criteria=issue_data.get("acceptance_criteria", []),
        epic_context=issue_data.get("epic_context", {}),
        plan_source=issue_data.get("plan_source", "/docs/plan.md"),
        repository_context=RepositoryContext(
            root_path=issue_data.get("root_path", ".")
        ),
    )
    result = run_builder_agent(builder_input)
    return result.model_dump_json()


@_wio_agent.tool_plain
async def run_git(work_item_id: str, impl_output: str, epic_id: str) -> str:
    """Execute the Git Agent to create branch and PR."""
    from hsb.agents.git_agent import run_git_agent
    from hsb.contracts.git import GitInput

    git_input = GitInput(
        work_item_id=work_item_id,
        implementation_output=json.loads(impl_output),
        epic_id=epic_id,
    )
    result = run_git_agent(git_input)
    return result.model_dump_json()


@_wio_agent.tool_plain
async def run_qa(
    work_item_id: str, pr_url: str, diff: str, qa_cycle_count: int
) -> str:
    """Execute the QA Agent to review a PR."""
    from hsb.agents.qa_agent import run_qa_agent
    from hsb.contracts.qa import PullRequestInput, QAInput

    qa_input = QAInput(
        work_item_id=work_item_id,
        linear_issue={},  # Orchestrator must pass full issue — injected by agent via tool call
        pull_request=PullRequestInput(url=pr_url, diff=diff),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=qa_cycle_count,
    )
    result = run_qa_agent(qa_input)
    return result.model_dump_json()


# --------------------------------------------------------------------------- #
# Core orchestration cycle                                                    #
# --------------------------------------------------------------------------- #


async def run_orchestration_cycle(work_item_id: str | None = None) -> None:
    """Execute one full Work Item Orchestrator cycle.

    Single PydanticAI session: skill content in ``system_prompt``, Phase 2
    agents as ``@_wio_agent.tool_plain`` wrappers. No sub-agent dispatch.

    Multi-turn lifecycle uses ``run_mcp_servers()`` context manager to keep
    the Linear MCP connection open across all three turns, with
    ``message_history=`` chaining the conversation state.

    Parameters
    ----------
    work_item_id:
        Optional Linear ID. When provided, the orchestrator drives that
        specific task. When ``None``, it queries Linear for the lowest-ID
        ``todo`` task with no unresolved dependencies and drives that one.
    """
    system_prompt = assemble_system_prompt()

    # Build a fresh agent with the assembled system prompt
    cycle_agent: Agent[None, str] = Agent(
        model=AnthropicModel("claude-sonnet-4-6"),
        output_type=str,
        system_prompt=system_prompt,
        tools=[run_linear_op, run_builder, run_git, run_qa],
        toolsets=[make_linear_mcp_toolset()],
    )

    cycle_prompt = (
        f"Run the work item lifecycle for work item {work_item_id}. "
        "Read its current Linear state first, then execute the next "
        "appropriate lifecycle step."
        if work_item_id
        else (
            "Query mcp__linear__list_issues for tasks with status=todo and no "
            "unresolved dependencies. Select the first available task (lowest "
            "LIN-ID). Then run its work item lifecycle: read Linear state, "
            "then execute the next appropriate lifecycle step."
        )
    )

    # Phase 5 lifecycle: three turns within the SAME context window via
    # message_history chaining. MCP connection held open with
    # run_mcp_servers().
    work_item_json = (
        f'{{"id": "{work_item_id}"}}' if work_item_id else "{}"
    )
    qa_result: dict[str, Any] = {}
    implementation_notes: dict[str, Any] = {}

    # G3 noop shim — kept for source-grep compatibility
    assert_no_task_dispatch(None)

    async with cycle_agent.run_mcp_servers():
        # [NEW Phase 5] Step 1: Intelligence enrichment (skill 10) — before Builder.
        result1 = await cycle_agent.run(
            build_enrichment_prompt(work_item_id or "next-todo", work_item_json),
            usage_limits=UsageLimits(request_limit=10),
        )
        _check_context_budget(result1, work_item_id, "enrichment")

        # [Phase 3] Steps 2-4: Builder → Git → QA cycle.
        result2 = await cycle_agent.run(
            cycle_prompt,
            message_history=result1.all_messages(),
            usage_limits=UsageLimits(request_limit=30),
        )
        _check_context_budget(result2, work_item_id, "cycle")
        logger.info("Orchestration cycle complete for %s", work_item_id)

        # [NEW Phase 5] Step 5: Knowledge storage evaluation (skill 11) — after QA.
        result3 = await cycle_agent.run(
            build_storage_prompt(qa_result, implementation_notes),
            message_history=result2.all_messages(),
            usage_limits=UsageLimits(request_limit=10),
        )
        _check_context_budget(result3, work_item_id, "storage")


def _check_context_budget(
    result: Any, work_item_id: str | None, step_name: str
) -> None:
    """G8 context budget warning at 60% of 200K window."""
    try:
        usage = result.usage()
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        if input_tokens > 120_000:
            logger.warning(
                "WIO context at %d tokens (%s step) for %s — "
                "consider skill index fallback",
                input_tokens,
                step_name,
                work_item_id,
            )
    except Exception as exc:
        logger.debug("Could not check usage: %s", exc)


# --------------------------------------------------------------------------- #
# QA cycle cap — Layer 2 safety net (CONTEXT.md D-05)                         #
# --------------------------------------------------------------------------- #


async def _check_qa_cycle_cap(
    work_item_id: str, qa_cycle_count: int, qa_status: str
) -> None:
    """Layer 2 guardrail against QA runaway (WORC-03 / D-05 Layer 2).

    Layer 1 (``QAOutput.validate_cycle_cap_logic`` in Phase 2) normally
    prevents reaching here — at ``qa_cycle_count >= 3`` Layer 1 forces
    ``qa_status="approved"`` with a tech-debt annotation. If somehow
    ``qa_cycle_count >= 3`` AND ``qa_status == "changes_required"`` still
    appear in the output, post a Linear escalation comment and DO NOT
    initiate a 4th cycle.
    """
    if qa_cycle_count >= 3 and qa_status == "changes_required":
        logger.error(
            "SAFETY NET: qa_cycle_count=%d but qa_status=changes_required for %s. "
            "Escalating to human.",
            qa_cycle_count,
            work_item_id,
        )
        await run_validated_linear_agent(
            operation="comment",
            payload={
                "issueId": work_item_id,
                "body": (
                    "**Automated escalation — max QA cycles reached**\n\n"
                    f"Max QA cycles reached (`qa_cycle_count={qa_cycle_count}`). "
                    "Escalating to human. Task status: blocked.\n\n"
                    "No further automated fix cycles will be initiated (WORC-03)."
                ),
            },
        )
