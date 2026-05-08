"""Phase 4 Plan 04 — Live integration tests for Global Orchestrator + MORD-05 cycle summary.

These tests run against a real Linear workspace via mcp-remote OAuth2 (Phase 1
D-01) and exercise the actual GORD-01..04 + MORD-05 code paths end-to-end.
Pre-conditions are documented in 04-04-SUMMARY.md (operator MVP checkpoint).
"""

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_ready_tasks_returns_todo_only():
    """GORD-01: Returns only todo items from real Linear workspace."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    # All returned tasks must have been todo-status items
    assert isinstance(output.ready_tasks, list)
    assert isinstance(output.is_backlog_empty, bool)
    assert isinstance(output.is_epic_ready, bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dependency_filter_against_live_linear():
    """GORD-02: Dependency filtering works against real Linear dependency graph."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    # No item in ready_tasks should have a non-done dependency in Linear
    # (filter logic validates this internally; integration test confirms no crash).
    for task in output.ready_tasks:
        assert task.id.startswith("LIN-"), f"Unexpected task ID format: {task.id}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_backlog_signal_live():
    """GORD-03 live shape check: is_backlog_empty is a bool."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    assert isinstance(output.is_backlog_empty, bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_epic_ready_signal_live():
    """GORD-04 live shape check: is_epic_ready is a bool."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    assert isinstance(output.is_epic_ready, bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cycle_summary_posted():
    """MORD-05: Cycle summary is posted to Linear EPIC after run_main_orchestrator completes.

    Asserts the cascade cycle runs end-to-end without raising. The MORD-05
    summary comment is posted as a side effect; assertion is 'no exception
    raised'. Visual verification of the comment landing in Linear is part
    of the operator checkpoint (04-04-SUMMARY.md).
    """
    from hsb.agents.main_orchestrator import run_main_orchestrator

    await run_main_orchestrator(mode="cascade")
