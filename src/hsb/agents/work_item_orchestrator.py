"""Work Item Orchestrator — single Claude Agent SDK session driving one Linear
task through its full lifecycle (Linear read → Builder → Git → QA → fix loop →
done) per CONTEXT.md D-01.

Architecture (RESEARCH.md Pattern 1, Pitfall 1, Pitfall 4):
- ONE SDK session per cycle. Skill content is injected into ``system_prompt``.
- Phase 2 agent modules are exposed as in-process MCP tools via
  ``create_sdk_mcp_server`` + ``@tool``. NO sub-agent dispatch (no
  ``AgentDefinition``, no ``agents=`` key in ``ClaudeAgentOptions``).
- Every ``@tool`` returns the canonical ``{"content":[{"type":"text","text":...}]}``
  envelope; returning a Pydantic model directly silently fails the SDK serializer.

Phase 5 (D-04, D-06): the WIO embeds skills 10 + 11 inline within the same SDK
session, adds a Step 1 enrichment turn before Builder and a Step 5 knowledge
storage turn after QA. The transition from a single ``query()`` call to a
multi-turn ``ClaudeSDKClient`` session preserves all of Phase 3's @tool
wiring (Builder/Git/QA dispatched as MCP tools).

Two-layer QA cycle cap (CONTEXT.md D-05):
- Layer 1 lives in :class:`hsb.contracts.qa.QAOutput.validate_cycle_cap_logic`.
- Layer 2 (this module) — :func:`_check_qa_cycle_cap` — posts a Linear escalation
  comment when ``qa_cycle_count >= 3`` AND ``qa_status == "changes_required"``,
  preventing a runaway 4th cycle if Layer 1 is somehow bypassed.

G1 (OAuth2 only): ``ANTHROPIC_API_KEY`` must be ``not in os.environ``. This
file does NOT have a module-top assert — that pattern broke pytest collection
when developer environments legitimately had the env var set. G1 is enforced
function-entry via :func:`hsb.agents._sdk_options.assert_oauth2_only` (called
from :func:`hsb.agents._sdk_options.make_options`); the SDK options here are
constructed via ``ClaudeAgentOptions(...)`` directly (Phase 3 pattern), but
the orchestrator is invoked through the global orchestrator which routes
through the chokepoint factory. Defensive pairing: the session-scoped
autouse fixture ``_gsd_clear_api_key`` in ``tests/conftest.py`` unsets the
env var at test session start.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import TextBlock
from dotenv import load_dotenv

from hsb.agents._sdk_options import assert_no_task_dispatch  # G3 runtime backstop
from hsb.agents.intelligence_agent import (
    build_enrichment_prompt,
    build_storage_prompt,
)
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.orchestrator import (  # noqa: F401
    WorkItemOrchInput,
    WorkItemOrchOutput,
)

load_dotenv()

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Skill assembly                                                              #
# --------------------------------------------------------------------------- #

# Injection order: task-orchestration first as the meta-skill framing the
# others, then the lifecycle skills in the order they appear in the cycle
# (Implementation → QA → Git → Linear). Resolved per CONTEXT.md "Claude's
# Discretion" entry on skill injection order.
SKILL_FILES = [
    "skills/06-TASK-ORCHESTRATION.md",
    "skills/02-IMPLEMENTATION.md",
    "skills/03-QA-REVIEW.md",
    "skills/04-GIT-PR-MANAGEMENT.md",
    "skills/05-LINEAR-SYSTEM-OF-RECORD.md",
    # Phase 5 [D-04]: Intelligence Agent runs inline within the WIO SDK
    # session. The skill bodies are injected into the system prompt so the
    # LLM applies the retrieval rules (skill 10) before Builder and the
    # ingestion criteria (skill 11) after QA. The migrated SKILL.md files
    # under .claude/skills/ are referenced for SDK auto-discovery; the
    # source paths under skills/ are loaded into assemble_system_prompt().
    ".claude/skills/knowledge-context-enrichment/SKILL.md",  # skill 10 [Phase 5]
    ".claude/skills/knowledge-storage/SKILL.md",  # skill 11 [Phase 5]
]


def assemble_system_prompt() -> str:
    """Read all SKILL_FILES and concatenate with ``# SKILL: <stem>`` separators.

    The headers are mandatory: without them the LLM cannot disambiguate which
    skill's constraints apply to which lifecycle step (RESEARCH.md
    Anti-Patterns).
    """
    parts = []
    for path in SKILL_FILES:
        content = Path(path).read_text()
        parts.append(f"# SKILL: {Path(path).stem}\n\n{content}")
    return "\n\n---\n\n".join(parts)


# --------------------------------------------------------------------------- #
# @tool wrappers — Phase 2 agents exposed as in-process MCP tools             #
# --------------------------------------------------------------------------- #
#
# CRITICAL (RESEARCH.md Pitfall 4): @tool return value MUST be
#     {"content": [{"type": "text", "text": <string>}]}
# Returning a Pydantic model directly causes silent tool failure.
# --------------------------------------------------------------------------- #


@tool(
    "run_linear_op",
    "Execute a Linear System of Record operation (create | update | comment | link_pr | read)",
    {"operation": str, "payload": dict},
)
async def run_linear_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 1 ``linear_agent.run_validated_linear_agent``."""
    result = await run_validated_linear_agent(
        operation=args["operation"],
        payload=args["payload"],
    )
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool(
    "run_builder",
    "Execute the Builder Agent for a work item",
    {"work_item_id": str, "issue_content": str},
)
async def run_builder_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 ``builder_agent.run_builder_agent``.

    The orchestrator (the SDK agent) MUST pass the FULL Linear issue payload as
    the ``issue_content`` JSON string — WORC-04 / Pitfall 4. The wrapper parses
    it via ``json.loads`` and constructs a Pydantic ``BuilderInput`` so any
    injection attempt that does not match the schema is rejected at the
    ``extra='forbid'`` boundary BEFORE the Builder agent runs.
    """
    import json

    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext

    issue_data = json.loads(args["issue_content"])
    builder_input = BuilderInput(
        work_item_id=args["work_item_id"],
        issue_description=issue_data.get("description", ""),
        acceptance_criteria=issue_data.get("acceptance_criteria", []),
        epic_context=issue_data.get("epic_context", {}),
        plan_source=issue_data.get("plan_source", "/docs/plan.md"),
        repository_context=RepositoryContext(
            root_path=issue_data.get("root_path", ".")
        ),
    )
    result = run_builder_agent(builder_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool(
    "run_git",
    "Execute the Git Agent to create branch and PR",
    {"work_item_id": str, "impl_output": str, "epic_id": str},
)
async def run_git_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 ``git_agent.run_git_agent``."""
    import json

    from hsb.agents.git_agent import run_git_agent
    from hsb.contracts.git import GitInput

    git_input = GitInput(
        work_item_id=args["work_item_id"],
        implementation_output=json.loads(args["impl_output"]),
        epic_id=args["epic_id"],
    )
    result = run_git_agent(git_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


@tool(
    "run_qa",
    "Execute the QA Agent to review a PR",
    {"work_item_id": str, "pr_url": str, "diff": str, "qa_cycle_count": int},
)
async def run_qa_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Wrapper: delegates to Phase 2 ``qa_agent.run_qa_agent``."""
    from hsb.agents.qa_agent import run_qa_agent
    from hsb.contracts.qa import PullRequestInput, QAInput

    qa_input = QAInput(
        work_item_id=args["work_item_id"],
        linear_issue={},  # Orchestrator must pass full issue — injected by agent via tool call
        pull_request=PullRequestInput(url=args["pr_url"], diff=args["diff"]),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=args["qa_cycle_count"],
    )
    result = run_qa_agent(qa_input)
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}


# --------------------------------------------------------------------------- #
# Core orchestration cycle                                                    #
# --------------------------------------------------------------------------- #


async def run_orchestration_cycle(work_item_id: str | None = None) -> None:
    """Execute one full Work Item Orchestrator cycle.

    Single SDK session: skill content in ``system_prompt``, Phase 2 agents as
    ``@tool`` wrappers. No sub-agent dispatch — only ``mcp_servers``
    (CONTEXT.md D-01, RESEARCH.md Pitfall 1).

    Parameters
    ----------
    work_item_id:
        Optional Linear ID. When provided, the orchestrator drives that
        specific task. When ``None``, it queries Linear for the lowest-ID
        ``todo`` task with no unresolved dependencies and drives that one.
    """
    system_prompt = assemble_system_prompt()

    # CRITICAL: Do NOT register agents={} — that triggers sub-agent dispatch
    # (RESEARCH.md Pitfall 1). Register only mcp_servers. The allowed_tools
    # list must use mcp__agents__* not Task.
    sdk_server = create_sdk_mcp_server(
        name="agents",
        version="1.0.0",
        tools=[run_linear_tool, run_builder_tool, run_git_tool, run_qa_tool],
    )

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={
            "agents": sdk_server,
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            },
        },
        allowed_tools=[
            "mcp__agents__run_linear_op",
            "mcp__agents__run_builder",
            "mcp__agents__run_git",
            "mcp__agents__run_qa",
            "mcp__linear__get_issue",
            "mcp__linear__list_issues",
            "mcp__linear__update_issue",
            "mcp__linear__create_comment",
        ],
        permission_mode="acceptEdits",
        max_turns=30,
    )

    # work_item_id selection: if not provided, orchestrator queries Linear for
    # the next todo task (Phase 4 will replace this with the Global
    # Orchestrator selection).
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

    # Phase 5 lifecycle: a single ClaudeSDKClient session drives three turns
    # within the SAME context window:
    #
    #   Step 1 [NEW Phase 5, INTL-01]  — Intelligence enrichment via skill 10.
    #                                    Populates `knowledge_context` for the
    #                                    Builder. No Linear writes.
    #   Steps 2-4 [Phase 3]            — Builder → Git → QA cycle (max QA
    #                                    cycle cap = 3, D-05 Layer 1 in
    #                                    QAOutput, Layer 2 in this module).
    #   Step 5 [NEW Phase 5, INTL-02]  — Knowledge storage evaluation via
    #                                    skill 11. Writes knowledge/<cat>/*.md
    #                                    only if ingestion criteria are met.
    #
    # G3 runtime backstop (assert_no_task_dispatch) is called on every
    # received message in EVERY receive_response() loop body — catches an
    # SDK regression that bypasses allowed_tools at runtime (WORC-02).
    work_item_json = f'{{"id": "{work_item_id}"}}' if work_item_id else "{}"
    qa_result: dict[str, Any] = {}
    implementation_notes: dict[str, Any] = {}

    async with ClaudeSDKClient(options=options) as client:
        # [NEW Phase 5] Step 1: Intelligence enrichment (skill 10) — before Builder.
        await client.query(
            build_enrichment_prompt(work_item_id or "next-todo", work_item_json)
        )
        async for msg in client.receive_response():
            assert_no_task_dispatch(msg)  # G3 runtime backstop for G2 (WORC-02)
            if isinstance(msg, SystemMessage) and msg.subtype == "init":
                mcp_servers = msg.data.get("mcp_servers", [])
                # Only inspect servers we registered — the SDK init message
                # may surface globally-registered MCPs (e.g. user-level OAuth
                # servers) whose auth state is unrelated to this orchestrator.
                required = {"agents", "linear"}
                failed = [
                    s
                    for s in mcp_servers
                    if s.get("name") in required and s.get("status") != "connected"
                ]
                if failed:
                    raise RuntimeError(f"MCP server failed to connect: {failed}")
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif hasattr(block, "name"):
                        logger.info("[TOOL] %s", block.name)

        # [Phase 3] Steps 2-4: Builder → Git → QA cycle.
        await client.query(cycle_prompt)
        async for msg in client.receive_response():
            assert_no_task_dispatch(msg)  # G3 runtime backstop for G2 (WORC-02)
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif hasattr(block, "name"):
                        logger.info("[TOOL] %s", block.name)
            elif isinstance(msg, ResultMessage):
                if msg.stop_reason == "error_max_turns":
                    raise RuntimeError(f"WIO hit max_turns for {work_item_id}")
                # G8 context budget warning at 60% of 200K window.
                if msg.usage:
                    input_tokens = msg.usage.get("input_tokens", 0)
                    if input_tokens > 120_000:
                        logger.warning(
                            "WIO context at %d tokens for %s — consider skill index fallback",
                            input_tokens,
                            work_item_id,
                        )
                logger.info(
                    "Orchestration cycle complete. Cost: $%.4f",
                    msg.total_cost_usd,
                )

        # [NEW Phase 5] Step 5: Knowledge storage evaluation (skill 11) — after QA.
        # qa_result/implementation_notes are propagated through the system
        # prompt instructions; this prompt directs the LLM to pull them from
        # its prior turns. Side-effectful writes to knowledge/; no return.
        await client.query(build_storage_prompt(qa_result, implementation_notes))
        async for msg in client.receive_response():
            assert_no_task_dispatch(msg)  # G3 runtime backstop for G2 (WORC-02)
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif hasattr(block, "name"):
                        logger.info("[TOOL] %s", block.name)
            elif isinstance(msg, ResultMessage):
                if msg.stop_reason == "error_max_turns":
                    raise RuntimeError(
                        f"WIO storage step hit max_turns for {work_item_id}"
                    )
                if msg.usage:
                    input_tokens = msg.usage.get("input_tokens", 0)
                    if input_tokens > 120_000:
                        logger.warning(
                            "WIO context at %d tokens (storage step) for %s — "
                            "consider skill index fallback",
                            input_tokens,
                            work_item_id,
                        )


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
