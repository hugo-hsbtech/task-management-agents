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

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.qa import QAInput, QAOutput

load_dotenv()
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
    "\nALLOWED ACTIONS: Read, gh pr diff, gh pr view only. "
    "\n\nREVIEW DIMENSIONS (skills/03-QA-REVIEW.md): "
    "1. Functional Correctness; 2. Acceptance Criteria Compliance; 3. Code Quality; "
    "4. Architecture Alignment; 5. Side Effects / Regression; 6. Edge Cases; 7. Test Coverage. "
    "\n\nOUTPUT FORMAT: Emit a single JSON object matching QAOutput schema. The schema "
    "FORBIDS extra fields. Cycle cap and findings cap are enforced by Pydantic — invalid "
    "output triggers a retry. Emit ONLY the JSON object."
)


async def _run_qa_agent_async(input: QAInput) -> QAOutput:
    base_prompt = (
        f"Review this PR for work item {input.work_item_id}:\n```json\n"
        f"{input.model_dump_json(indent=2)}\n```\n\n"
        f"Return ONLY a JSON object matching QAOutput schema. "
        f"Reminder: input qa_cycle_count={input.qa_cycle_count} -> output qa_cycle_count="
        f"{input.qa_cycle_count + 1}. "
        f"{'You MUST approve with tech_debt_annotation (cycle cap reached).' if input.qa_cycle_count == 2 else ''}"
    )

    options = ClaudeAgentOptions(
        model="claude-opus-4-7",
        allowed_tools=[
            "Read",
            "Bash(gh pr diff *)",
            "Bash(gh pr view *)",
        ],
        # NO mcp_servers, NO Edit/Write, NO Bash patterns for git/gh pr create/gh pr merge
        permission_mode="acceptEdits",
        system_prompt=QA_SYSTEM_PROMPT,
        max_turns=20,
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
                    raise RuntimeError(f"QA Agent failed: {message.subtype}")

        if result_text is None:
            logger.warning("Attempt %d: no result text", attempt)
            continue
        try:
            json_start = result_text.index("{")
            json_end = result_text.rindex("}") + 1
            raw = json.loads(result_text[json_start:json_end])
            output = QAOutput.model_validate(
                raw
            )  # model_validator runs HERE — cycle cap enforced
            logger.info("QA Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning("Attempt %d failed: %s", attempt, e)
            prompt = base_prompt + (
                f"\n\nPrevious attempt produced invalid output:\n{e}\n"
                "Return corrected JSON ONLY. Cycle cap and findings cap are Pydantic-enforced."
            )

    raise ValueError(
        f"QA Agent failed validation after {MAX_VALIDATION_RETRIES} attempts: {last_error}"
    )


def _write_qa_results_to_linear(work_item_id: str, output: QAOutput) -> None:
    """Persist QA results to Linear via Phase 1 service.

    Called AFTER QAOutput is validated — never inside the agent loop (D-04, QAAG-05).
    Writes:
      1. qa_cycle_count increment on the work item
      2. fix subtasks (max 5) when qa_status == changes_required
    """
    # 1. Increment qa_cycle_count
    asyncio.run(
        run_validated_linear_agent(
            operation="update",
            payload={
                "issueId": work_item_id,
                "qa_cycle_count": output.qa_cycle_count,
                "qa_status": output.qa_status,
            },
        )
    )
    # 2. Create fix subtasks for blocking findings (max 5 by schema)
    if output.qa_status == "changes_required" and output.findings:
        subtasks = [
            {
                "title": f.suggested_subtask.title
                if f.suggested_subtask
                else f"[FIX] {f.title}",
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
            asyncio.run(
                run_validated_linear_agent(
                    operation="create_subtasks",
                    payload={"parentId": work_item_id, "subtasks": subtasks},
                )
            )


def run_qa_agent(input: QAInput) -> QAOutput:
    """Synchronous entry point. Runs agent, validates output, then writes to Linear.

    The Linear write is INTENTIONALLY outside the agent loop (D-04, QAAG-05): the agent
    has zero Linear MCP access; the Python integration layer calls run_validated_linear_agent
    only after QAOutput.model_validate succeeds (cycle cap + findings cap both enforced).
    """
    output = asyncio.run(_run_qa_agent_async(input))
    _write_qa_results_to_linear(input.work_item_id, output)
    return output
