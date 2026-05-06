"""Phase 4 Plan 02 — Filled-in unit tests for Global Orchestrator (GORD-01..04).

Behavior tests now exercise the real GlobalOrchestrator implementation. Functional
contract validation tests for GlobalOrchestratorOutput remain unchanged.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask


# --- GORD-01: Returns only todo items sorted by priority ---

def test_returns_todo_only():
    """GORD-01: Only items with status='todo' and resolved dependencies are returned."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-1", "status": "todo", "priority": 2, "createdAt": "2024-01-01", "type": "task", "dependencies": [], "title": "Task 1"},
        {"id": "LIN-2", "status": "done", "priority": 1, "createdAt": "2024-01-02", "type": "task", "dependencies": [], "title": "Task 2"},
        {"id": "LIN-3", "status": "in_progress", "priority": 3, "createdAt": "2024-01-03", "type": "task", "dependencies": [], "title": "Task 3"},
    ]
    go = GlobalOrchestrator()
    result = go._filter_ready_items(mock_items)
    assert len(result) == 1
    assert result[0]["id"] == "LIN-1"


# --- GORD-02: Dependency filter ---

def test_dependency_filter():
    """GORD-02: Items with non-done blocking dependencies are excluded."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-10", "status": "todo", "priority": 1, "createdAt": "2024-01-01", "type": "task", "dependencies": ["LIN-11"], "title": "Blocked task"},
        {"id": "LIN-11", "status": "todo", "priority": 2, "createdAt": "2024-01-02", "type": "task", "dependencies": [], "title": "Blocking task"},
    ]
    go = GlobalOrchestrator()
    result = go._filter_ready_items(mock_items)
    # LIN-10 is excluded (LIN-11 not done); LIN-11 is included (no deps)
    assert len(result) == 1
    assert result[0]["id"] == "LIN-11"


# --- GORD-03: Empty backlog detection ---

@pytest.mark.asyncio
async def test_empty_backlog_signal():
    """GORD-03: Returns is_backlog_empty=True when project has no work items."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    go = GlobalOrchestrator()
    with patch.object(go, "_fetch_all_items", new_callable=AsyncMock, return_value=[]):
        output = await go.get_ready_tasks()
    assert output.is_backlog_empty is True
    assert output.ready_tasks == []
    assert output.is_epic_ready is False


# --- GORD-04: EPIC completion detection ---

@pytest.mark.asyncio
async def test_epic_ready_signal():
    """GORD-04: Returns is_epic_ready=True when all children are done + qa_approved."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    mock_items = [
        {"id": "LIN-100", "status": "in_progress", "type": "epic", "priority": 1, "createdAt": "2024-01-01", "dependencies": [], "title": "EPIC"},
        {"id": "LIN-101", "status": "done", "qa_status": "approved", "type": "task", "priority": 2, "createdAt": "2024-01-02", "dependencies": [], "title": "Task 1"},
        {"id": "LIN-102", "status": "done", "qa_status": "approved", "type": "task", "priority": 2, "createdAt": "2024-01-03", "dependencies": [], "title": "Task 2"},
    ]
    go = GlobalOrchestrator()
    with patch.object(go, "_fetch_all_items", new_callable=AsyncMock, return_value=mock_items):
        output = await go.get_ready_tasks()
    assert output.is_epic_ready is True
    assert output.ready_tasks == []  # No todo items


# --- Contract validation (functional) ---

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
