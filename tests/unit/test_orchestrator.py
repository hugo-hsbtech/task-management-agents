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
    """WORC-02 / RESEARCH.md Pitfall 1: ClaudeAgentOptions must register only
    ``mcp_servers``. AST inspection must show NO ``AgentDefinition`` reference
    and NO ``agents=`` keyword in any call to ``ClaudeAgentOptions(...)``."""
    import ast

    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    source = inspect.getsource(run_orchestration_cycle)
    tree = ast.parse(source)

    # Walk the AST, fail if any Call to ClaudeAgentOptions has an `agents`
    # keyword, or if any Name node references AgentDefinition.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "AgentDefinition":
            pytest.fail(
                "AgentDefinition reference detected in run_orchestration_cycle "
                "— sub-agent dispatch is forbidden by D-01 / Pitfall 1."
            )
        if isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", None) or getattr(
                node.func, "attr", None
            )
            if func_name == "ClaudeAgentOptions":
                for kw in node.keywords:
                    assert kw.arg != "agents", (
                        "agents= kwarg in ClaudeAgentOptions means sub-agent "
                        "dispatch. Must use mcp_servers only."
                    )

    # Positive checks: the canonical MCP-server path must be present.
    assert "mcp_servers" in source
    assert "create_sdk_mcp_server" in source


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
    """WORC-04 / Pitfall 4: ``run_builder_tool`` must accept ``issue_content``
    as a structured JSON string and parse it before constructing
    ``BuilderInput`` — never read context-window state.

    The ``@tool`` decorator wraps the function in an ``SdkMcpTool`` object;
    its ``.handler`` attribute exposes the underlying coroutine function so
    ``inspect.getsource`` works.
    """
    from hsb.agents.work_item_orchestrator import run_builder_tool

    # SDK 0.1+: @tool returns an SdkMcpTool whose .handler is the function
    fn = getattr(run_builder_tool, "handler", run_builder_tool)
    source = inspect.getsource(fn)
    assert "issue_content" in source
    assert "json.loads" in source or "model_validate" in source
    # Schema declares issue_content as str so the LLM is forced to pass JSON,
    # not a dict (Pitfall 4 + WORC-04).
    assert run_builder_tool.input_schema.get("issue_content") is str


def test_full_context_in_tool_calls() -> None:
    """WORC-04 alias matching VALIDATION.md command ID."""
    test_tool_wrapper_requires_full_issue_content()


def test_all_tools_return_canonical_envelope() -> None:
    """Pitfall 4: every @tool wrapper must return
    ``{"content": [{"type": "text", "text": ...}]}``."""
    from hsb.agents import work_item_orchestrator as wio

    src = inspect.getsource(wio)
    # 4 wrappers × one canonical-shape return statement each
    matches = src.count('"content": [{"type": "text", "text":')
    assert matches >= 4, (
        f"expected at least 4 canonical-envelope returns, found {matches}"
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
    """``run_orchestration_cycle`` source must list all four
    ``mcp__agents__run_*`` tools and at least 4 ``mcp__linear__*`` tools."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    source = inspect.getsource(run_orchestration_cycle)
    for required in (
        "mcp__agents__run_linear_op",
        "mcp__agents__run_builder",
        "mcp__agents__run_git",
        "mcp__agents__run_qa",
    ):
        assert required in source, f"missing required tool: {required}"
    assert source.count("mcp__linear__") >= 4
    # Hard caps to prevent runaway cycles (T-3-03)
    assert "max_turns=30" in source
    assert 'permission_mode="acceptEdits"' in source


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
