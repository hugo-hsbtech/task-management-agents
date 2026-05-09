"""QA Agent — reviews PR diff against Linear work item.

QAAG-05: NO Edit, NO Write, NO git, NO Linear MCP in agent loop.
D-04: Linear writes (qa_cycle_count increment, fix subtask creation) happen OUTSIDE
the agent loop via Phase 1 service — see _write_qa_results_to_linear below.
QAAG-04 / Pitfall 2: cycle cap enforced by QAOutput.model_validator (Pydantic), not just
system prompt. The model_validator runs INSIDE QAOutput.model_validate(raw) and
rejects invalid (qa_cycle_count>=3 + changes_required) combinations.
"""
from __future__ import annotations

import asyncio
import logging

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.usage import UsageLimits

from hsb.agents.filesystem_tools import read_file
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.agents.subprocess_tools import gh_pr_diff, gh_pr_view
from hsb.contracts.qa import QAInput, QAOutput

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3

QA_SYSTEM_PROMPT = (
    "You are the QA Agent for HSBTech. Review the PR diff against the Linear work item "
    "requirements provided in the input contract. "
    "\n\nQA CYCLE CAP (QAAG-04, D-05): Read qa_cycle_count from the input contract "
    "(0-indexed: 0=first review, 1=second, 2=third). "
    "If qa_cycle_count == 2 (this is the THIRD review), you MUST emit qa_status='approved' "
    "with a tech_debt_annotation describing the unresolved issues. NEVER request a 4th fix cycle. "
    "Output qa_cycle_count in the result is 1-indexed (1=first done, 2=second, 3=third). "
    "So input qa_cycle_count=2 -> output qa_cycle_count=3 with status='approved' + annotation. "
    "\n\nFIX SUBTASK CAP (QAAG-03): Maximum 5 findings per report. Consolidate if needed. "
    "Each finding's suggested_subtask.title MUST start with '[FIX] '. "
    "\n\nCAPABILITY BOUNDARY (QAAG-05): You MUST NOT: "
    "- Edit or Write any source files. "
    "- Create PRs or branches. "
    "- Run git commands directly. "
    "- Call any Linear MCP tool (you have none — Linear writes happen post-validation). "
    "\nALLOWED ACTIONS: read_file, gh_pr_diff, gh_pr_view only. "
    "\n\nREVIEW DIMENSIONS (skills/03-QA-REVIEW.md): "
    "1. Functional Correctness; 2. Acceptance Criteria Compliance; 3. Code Quality; "
    "4. Architecture Alignment; 5. Side Effects / Regression; 6. Edge Cases; 7. Test Coverage. "
    "\n\nOUTPUT FORMAT: Return a QAOutput object. The schema FORBIDS extra fields. "
    "Cycle cap and findings cap are enforced by Pydantic — invalid output triggers a retry."
)

_qa_agent: Agent[None, QAOutput] = Agent(
    model=AnthropicModel("claude-opus-4-7"),
    output_type=QAOutput,
    system_prompt=QA_SYSTEM_PROMPT,
    tools=[read_file, gh_pr_diff, gh_pr_view],
    output_retries=MAX_VALIDATION_RETRIES,
)


async def _run_qa_agent_async(input: QAInput) -> QAOutput:
    prompt = (
        f"Review this PR for work item {input.work_item_id}:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Return a QAOutput object. "
        f"Reminder: input qa_cycle_count={input.qa_cycle_count} -> output qa_cycle_count="
        f"{input.qa_cycle_count + 1}. "
        f"{'You MUST approve with tech_debt_annotation (cycle cap reached).' if input.qa_cycle_count == 2 else ''}"
    )

    result = await _qa_agent.run(
        prompt,
        usage_limits=UsageLimits(request_limit=20),
    )
    return result.output


def _write_qa_results_to_linear(work_item_id: str, output: QAOutput) -> None:
    """Persist QA results to Linear via Phase 1 service.

    Called AFTER QAOutput is validated — never inside the agent loop (D-04, QAAG-05).
    Writes:
      1. qa_cycle_count increment on the work item
      2. fix subtasks (max 5) when qa_status == changes_required
    """
    # 1. Increment qa_cycle_count
    asyncio.run(run_validated_linear_agent(
        operation="update",
        payload={
            "issueId": work_item_id,
            "qa_cycle_count": output.qa_cycle_count,
            "qa_status": output.qa_status,
        },
    ))
    # 2. Create fix subtasks for blocking findings (max 5 by schema)
    if output.qa_status == "changes_required" and output.findings:
        subtasks = [
            {
                "title": f.suggested_subtask.title if f.suggested_subtask else f"[FIX] {f.title}",
                "description": (
                    f.suggested_subtask.description
                    if f.suggested_subtask
                    else f"Problem: {f.problem}\n\nSuggested fix: {f.suggested_fix}"
                ),
            }
            for f in output.findings
            if f.status == "blocking"
        ][:5]  # defense-in-depth: schema already enforces max 5 findings
        if subtasks:
            asyncio.run(run_validated_linear_agent(
                operation="create_subtasks",
                payload={"parentId": work_item_id, "subtasks": subtasks},
            ))


def run_qa_agent(input: QAInput) -> QAOutput:
    """Synchronous entry point. Runs agent, validates output, then writes to Linear.

    The Linear write is INTENTIONALLY outside the agent loop (D-04, QAAG-05): the agent
    has zero Linear MCP access; the Python integration layer calls run_validated_linear_agent
    only after QAOutput.model_validate succeeds (cycle cap + findings cap both enforced).
    """
    output = asyncio.run(_run_qa_agent_async(input))
    _write_qa_results_to_linear(input.work_item_id, output)
    return output
