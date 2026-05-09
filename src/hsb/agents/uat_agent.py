"""UAT Agent — standalone Claude Agent SDK session validating User Stories
against acceptance criteria. Pattern B (AI-SPEC §3) — ``query()`` one-shot.

Scope structural enforcement:
- ``allowed_tools=['Read', 'Glob', 'Grep', 'Bash']`` — no Write/Edit/Agent.
- ``mcp_servers=None`` — User Story JSON is in the prompt; cannot write to Linear.
- This module does NOT import ``hsb.agents.linear_agent``.
- :func:`run_uat_and_validate` does NOT modify Linear state — Plan 05-04
  is responsible for routing fix subtasks through the Linear Agent path.

G1 (OAuth2-only) is enforced at the SDK construction chokepoint
(:func:`hsb.agents._sdk_options.assert_oauth2_only`, called from
:func:`hsb.agents._sdk_options.make_options`). NO module-top OAuth2
assertion here — the previous plan revision had one and broke pytest
collection when ``ANTHROPIC_API_KEY`` was set in the developer
environment for unrelated reasons.

G3 backstop: :func:`hsb.agents._sdk_options.assert_no_task_dispatch` is
called inside the ``async for msg in query(...)`` receive loop on every
message — catches an SDK regression that bypasses ``allowed_tools``
enforcement at runtime.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    query,
)
from claude_agent_sdk.types import TextBlock
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.agents._sdk_options import assert_no_task_dispatch, make_options
from hsb.contracts.uat import UATResult

load_dotenv()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def load_skill(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


async def run_uat_and_validate(
    user_story_id: str,
    acceptance_criteria: list[str],
    uat_cycle: int,
) -> UATResult:
    """Standalone Claude Agent SDK session. Skill 08 inline (Pattern B).

    UATA-04: ``allowed_tools=['Read','Glob','Grep','Bash']`` — no Write/Edit/Agent.
    UATA-04: ``mcp_servers=None`` — User Story JSON is in the prompt.

    Returns validated :class:`UATResult`. Raises ``RuntimeError`` after
    :data:`MAX_RETRIES` failed validation attempts — never returns an
    unvalidated result.

    WORC-02: ``"Agent"`` is absent from ``allowed_tools`` — no
    sub-subagent dispatch.
    """
    skill_08 = load_skill(".claude/skills/uat-validation/SKILL.md")
    schema_json = json.dumps(UATResult.model_json_schema(), indent=2)
    scope_block = "\n".join(
        f"[AC-{i + 1}] {c}" for i, c in enumerate(acceptance_criteria)
    )

    base_prompt = (
        f"Validate User Story {user_story_id} (UAT cycle {uat_cycle}).\n\n"
        "SCOPE BOUNDARY: Only validate the acceptance criteria listed below. "
        "Do not evaluate any feature, behavior, or quality dimension not "
        "explicitly listed. Any finding that lacks a direct reference to a "
        "listed [AC-N] criterion is out of scope and must not appear in your "
        "response.\n\n"
        f"Acceptance criteria:\n{scope_block}\n\n"
        f"Return a single JSON object matching this schema:\n{schema_json}\n"
        "Do not include any prose before or after the JSON."
    )

    options = make_options(
        system_prompt=skill_08,
        allowed_tools=["Read", "Glob", "Grep", "Bash"],
        permission_mode="dontAsk",
        max_turns=20,
        model="claude-sonnet-4-6",
        mcp_servers=None,
    )
    # UATA-04 structural assertions (defense-in-depth):
    assert "Write" not in options.allowed_tools, (
        "UATA-04: UAT Agent must not have Write tool"
    )
    assert "Edit" not in options.allowed_tools, (
        "UATA-04: UAT Agent must not have Edit tool"
    )
    assert "Agent" not in options.allowed_tools, "G2 / WORC-02: 'Agent' must not appear"
    assert getattr(options, "mcp_servers", None) in (None, {}), (
        "UATA-04: UAT Agent must not have mcp_servers"
    )

    last_error: str | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        prompt = base_prompt
        if last_error:
            prompt += (
                f"\n\nPrevious attempt failed validation: {last_error}. Fix and retry."
            )

        result_text = ""
        async for msg in query(prompt=prompt, options=options):
            # G3 (AI-SPEC §6) runtime backstop for G2 — catches an SDK
            # regression that bypasses allowed_tools enforcement at runtime
            # by detecting any tool_use_block named "Task" in
            # AssistantMessage.content. Propagates RuntimeError on
            # violation; the SDK session aborts.
            assert_no_task_dispatch(msg)
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
            if isinstance(msg, ResultMessage):
                if msg.stop_reason == "error_max_turns":
                    raise RuntimeError(f"UAT Agent hit max_turns for {user_story_id}")
                result_text = msg.result or ""

        try:
            clean = (
                result_text.strip().removeprefix("```json").removesuffix("```").strip()
            )
            data = json.loads(clean)
            data.setdefault("user_story_id", user_story_id)
            data.setdefault("uat_cycle", uat_cycle)
            return UATResult(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning(
                "UATResult validation failed (attempt %d/%d) for %s: %s",
                attempt,
                MAX_RETRIES,
                user_story_id,
                last_error,
            )

    raise RuntimeError(
        f"UAT Agent failed to produce valid UATResult after {MAX_RETRIES} "
        f"attempts for {user_story_id}. Last error: {last_error}"
    )
