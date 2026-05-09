"""Plan 03-02 — Work Item Orchestrator unit tests.

Phase 3 behavior tests for WORC-02/03/04 + contract-validation tests against
the pydantic models from Plan 03-01.

VALIDATION.md command IDs (alias tests below match these):
- WORC-02: ``test_no_subagent_dispatch``
- WORC-03: ``test_qa_cycle_cap``
- WORC-04: ``test_full_context_in_tool_calls``
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from hsb.contracts.orchestrator import WorkItemOrchInput, WorkItemOrchOutput


# --- WORC-02: No sub-agent dispatch -----------------------------------------

def test_no_subagent_dispatch_in_options() -> None:
    """WORC-02: PydanticAI Agent must not dispatch sub-agents. AST inspection
    must show NO ``AgentDefinition`` reference."""
    import ast

    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    source = inspect.getsource(run_orchestration_cycle)
    tree = ast.parse(source)

    # Walk the AST, fail if any Name node references AgentDefinition.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "AgentDefinition":
            pytest.fail(
                "AgentDefinition reference detected in run_orchestration_cycle "
                "— sub-agent dispatch is forbidden by D-01 / Pitfall 1."
            )

    # PydanticAI patterns: Agent must be used, with toolsets for MCP and
    # message_history for multi-turn (replaces ClaudeSDKClient).
    assert "Agent(" in source or "cycle_agent" in source
    assert "message_history" in source


def test_no_subagent_dispatch() -> None:
    """WORC-02 alias matching VALIDATION.md command ID."""
    test_no_subagent_dispatch_in_options()


# --- WORC-03: QA cycle cap (Layer 1 + Layer 2) ------------------------------

def test_qa_cycle_cap_model_validator() -> None:
    """WORC-03 / QAAG-04 Layer 1: qa_cycle_count >= 3 + changes_required is rejected
    by the QAOutput model_validator (Phase 2)."""
    from hsb.contracts.qa import QAOutput

    with pytest.raises(ValidationError, match="qa_cycle_count >= 3"):
        QAOutput.model_validate(
            {
                "work_item_id": "LIN-123",
                "qa_status": "changes_required",
                "qa_cycle_count": 3,
                "summary": "Still failing",
                "findings": [],
            }
        )


def test_qa_cycle_cap() -> None:
    """WORC-03 alias matching VALIDATION.md command ID."""
    test_qa_cycle_cap_model_validator()


@pytest.mark.asyncio
async def test_qa_cycle_cap_safety_net_posts_comment() -> None:
    """WORC-03 Layer 2: ``_check_qa_cycle_cap`` posts an escalation comment via
    ``run_validated_linear_agent`` when ``qa_cycle_count >= 3`` and
    ``qa_status == 'changes_required'``."""
    from hsb.agents.work_item_orchestrator import _check_qa_cycle_cap

    with patch(
        "hsb.agents.work_item_orchestrator.run_validated_linear_agent",
        new_callable=AsyncMock,
    ) as mock_linear:
        mock_linear.return_value = MagicMock(
            model_dump_json=lambda: '{"result": "success"}'
        )
        await _check_qa_cycle_cap(
            "LIN-123", qa_cycle_count=3, qa_status="changes_required"
        )

    mock_linear.assert_called_once()
    # operation may be passed positionally or by keyword — check both
    call_args, call_kwargs = mock_linear.call_args
    operation = call_kwargs.get("operation") or (call_args[0] if call_args else None)
    payload = call_kwargs.get("payload") or (call_args[1] if len(call_args) > 1 else {})
    assert operation == "comment", f"expected operation='comment', got {operation!r}"
    assert "Max QA cycles reached" in payload["body"]


@pytest.mark.asyncio
async def test_qa_cycle_cap_safety_net_silent_below_cap() -> None:
    """WORC-03 Layer 2: below-cap states must NOT call Linear."""
    from hsb.agents.work_item_orchestrator import _check_qa_cycle_cap

    with patch(
        "hsb.agents.work_item_orchestrator.run_validated_linear_agent",
        new_callable=AsyncMock,
    ) as mock_linear:
        await _check_qa_cycle_cap("LIN-9", qa_cycle_count=2, qa_status="changes_required")
        await _check_qa_cycle_cap("LIN-9", qa_cycle_count=3, qa_status="approved")
    mock_linear.assert_not_called()


# --- WORC-04: Full context passed in tool calls -----------------------------

def test_tool_wrapper_requires_full_issue_content() -> None:
    """WORC-04 / Pitfall 4: ``run_builder`` tool must accept ``issue_content``
    as a structured JSON string and parse it before constructing
    ``BuilderInput`` — never read context-window state.

    PydanticAI: ``@_wio_agent.tool_plain`` decorates the underlying coroutine
    function directly. We use ``inspect.signature`` to verify typing.
    """
    from hsb.agents.work_item_orchestrator import run_builder

    # PydanticAI: tools are registered via @_wio_agent.tool_plain; the
    # underlying function is callable directly.
    sig = inspect.signature(run_builder)
    params = sig.parameters
    assert "issue_content" in params, "run_builder must accept issue_content"
    assert "work_item_id" in params, "run_builder must accept work_item_id"
    # Type annotation must be str so the LLM is forced to pass JSON
    # (from __future__ import annotations makes annotations strings, so check both)
    assert params["issue_content"].annotation in (str, "str")
    assert params["work_item_id"].annotation in (str, "str")


def test_full_context_in_tool_calls() -> None:
    """WORC-04 alias matching VALIDATION.md command ID."""
    test_tool_wrapper_requires_full_issue_content()


def test_all_tools_return_str() -> None:
    """PydanticAI tools return str (model_dump_json); no MCP envelope needed."""
    from hsb.agents import work_item_orchestrator as wio

    src = inspect.getsource(wio)
    # 4 PydanticAI tools must return model_dump_json() strings
    matches = src.count("model_dump_json()")
    assert matches >= 4, (
        f"expected at least 4 model_dump_json() returns from tools, found {matches}"
    )


# --- assemble_system_prompt -------------------------------------------------

def test_assemble_system_prompt_loads_all_skills() -> None:
    """``assemble_system_prompt`` reads all 5 SKILL_FILES with ``# SKILL:``
    headers and returns a string > 5000 chars (skills total ~12KB)."""
    from hsb.agents.work_item_orchestrator import assemble_system_prompt, SKILL_FILES

    prompt = assemble_system_prompt()
    assert len(prompt) > 5000, f"system prompt is only {len(prompt)} chars"
    for path in SKILL_FILES:
        from pathlib import Path
        stem = Path(path).stem
        assert f"# SKILL: {stem}" in prompt, f"missing skill header for {stem}"


def test_orchestration_options_lists_required_tools() -> None:
    """``run_orchestration_cycle`` registers all four Phase 2 agent tools and
    sets a request_limit usage cap (replaces max_turns)."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    source = inspect.getsource(run_orchestration_cycle)
    # PydanticAI: tools are registered via @_wio_agent.tool_plain, referenced
    # by function name in tools=[...] of the cycle agent
    for required in (
        "run_linear_op",
        "run_builder",
        "run_git",
        "run_qa",
    ):
        assert required in source, f"missing required tool: {required}"
    # Linear MCP toolset is wired via make_linear_mcp_toolset
    assert "make_linear_mcp_toolset" in source or "Linear" in source
    # Hard caps to prevent runaway cycles (T-3-03) — UsageLimits replaces max_turns
    assert "request_limit=" in source
    assert "UsageLimits" in source


# --- Contract validation (Task 1 deliverables — implemented now) -------------

def test_valid_orch_output_passes() -> None:
    """Sanity: a fully-populated WorkItemOrchOutput dict validates."""
    output = WorkItemOrchOutput.model_validate(
        {
            "work_item_id": "LIN-123",
            "lifecycle_status": "done",
            "next_skill": None,
            "handoff_payload": {},
            "lifecycle_summary": "Task completed successfully. QA approved on first cycle.",
        }
    )
    assert output.lifecycle_status == "done"
    assert output.next_skill is None
    assert output.handoff_payload == {}


def test_invalid_lifecycle_status_fails() -> None:
    """A lifecycle_status not in the Literal enum is rejected."""
    with pytest.raises(ValidationError):
        WorkItemOrchOutput.model_validate(
            {
                "work_item_id": "LIN-123",
                "lifecycle_status": "unknown_status",
                "handoff_payload": {},
                "lifecycle_summary": "x",
            }
        )


def test_orch_output_extra_field_rejected() -> None:
    """extra='forbid' rejects unexpected fields (T-3-01 mitigation)."""
    with pytest.raises(ValidationError):
        WorkItemOrchOutput.model_validate(
            {
                "work_item_id": "LIN-123",
                "lifecycle_status": "done",
                "handoff_payload": {},
                "lifecycle_summary": "done",
                "unexpected_field": "boom",
            }
        )


def test_orch_input_extra_field_rejected() -> None:
    """extra='forbid' applies to WorkItemOrchInput too."""
    with pytest.raises(ValidationError):
        WorkItemOrchInput.model_validate(
            {
                "work_item": {"id": "LIN-1"},
                "epic_context": {},
                "linear_state": {},
                "extra": "boom",
            }
        )
