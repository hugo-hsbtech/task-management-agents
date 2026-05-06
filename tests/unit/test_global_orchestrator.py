"""Phase 4 Plan 01 — Wave 0 stubs for Global Orchestrator behavior tests.

Stubs for GORD-01..04 plus functional contract validation tests for
GlobalOrchestratorOutput. Behavior stubs fail with the literal string
"Wave 0 stub" so a grep can confirm completeness (Nyquist enforcement).
Stubs are filled in by Plan 02 (Global Orchestrator implementation).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask


# --- GORD-01: Returns only todo items sorted by priority ---

@pytest.mark.asyncio
async def test_returns_todo_only():
    """GORD-01: Only items with status='todo' and resolved dependencies are returned."""
    pytest.fail("Wave 0 stub — implemented in Plan 02")


# --- GORD-02: Dependency filter ---

@pytest.mark.asyncio
async def test_dependency_filter():
    """GORD-02: Items with non-done blocking dependencies are excluded."""
    pytest.fail("Wave 0 stub — implemented in Plan 02")


# --- GORD-03: Empty backlog detection ---

@pytest.mark.asyncio
async def test_empty_backlog_signal():
    """GORD-03: Returns is_backlog_empty=True when project has no work items."""
    pytest.fail("Wave 0 stub — implemented in Plan 02")


# --- GORD-04: EPIC completion detection ---

@pytest.mark.asyncio
async def test_epic_ready_signal():
    """GORD-04: Returns is_epic_ready=True when all children are done + qa_approved."""
    pytest.fail("Wave 0 stub — implemented in Plan 02")


# --- Contract validation (functional — passes at Wave 0) ---

def test_global_orchestrator_output_contract():
    """GlobalOrchestratorOutput schema validates correctly."""
    output = GlobalOrchestratorOutput.model_validate({
        "ready_tasks": [{"id": "LIN-1", "title": "Task 1"}],
        "is_backlog_empty": False,
        "is_epic_ready": False,
    })
    assert output.ready_tasks[0].id == "LIN-1"
    assert output.ready_tasks[0].priority == 999
    assert output.ready_tasks[0].dependencies == []


def test_global_orchestrator_output_extra_field_rejected():
    """GlobalOrchestratorOutput rejects extra fields (extra='forbid')."""
    with pytest.raises(ValidationError):
        GlobalOrchestratorOutput.model_validate({
            "ready_tasks": [],
            "is_backlog_empty": True,
            "is_epic_ready": False,
            "unexpected_field": "boom",
        })
