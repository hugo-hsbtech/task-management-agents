"""Wave 0 / Plan 03-01 — Work Item Orchestrator unit test stubs.

Three contract validation tests are functional NOW (they exercise the pydantic
models from Task 1). The four behavior tests are stubs that fail with
"Wave 0 stub" until Plan 02 ships ``hsb.agents.work_item_orchestrator``.

VALIDATION.md mappings (per 03-VALIDATION.md):
- WORC-02: ``test_no_subagent_dispatch`` (alias of canonical test below)
- WORC-03: ``test_qa_cycle_cap`` (alias for the two cycle-cap tests below)
- WORC-04: ``test_full_context_in_tool_calls`` (alias)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hsb.contracts.orchestrator import WorkItemOrchInput, WorkItemOrchOutput


# --- WORC-02: No sub-agent dispatch -----------------------------------------

def test_no_subagent_dispatch_in_options() -> None:
    """WORC-02: ClaudeAgentOptions must not register agents={} — only mcp_servers."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


def test_no_subagent_dispatch() -> None:
    """WORC-02 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


# --- WORC-03: QA cycle cap (Layer 1 + Layer 2) ------------------------------

def test_qa_cycle_cap_model_validator() -> None:
    """WORC-03 / QAAG-04 Layer 1: qa_cycle_count >= 3 + changes_required is rejected."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


def test_qa_cycle_cap() -> None:
    """WORC-03 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


@pytest.mark.asyncio
async def test_qa_cycle_cap_safety_net_posts_comment() -> None:
    """WORC-03 Layer 2: orchestrator safety net posts escalation comment when cap reached."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


# --- WORC-04: Full context passed in tool calls -----------------------------

def test_tool_wrapper_requires_full_issue_content() -> None:
    """WORC-04: run_builder_tool must accept issue_content as a structured JSON string."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


def test_full_context_in_tool_calls() -> None:
    """WORC-04 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 (work_item_orchestrator.py)")


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
