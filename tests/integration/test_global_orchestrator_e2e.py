"""Phase 4 Plan 01 — Wave 0 integration stubs for Global Orchestrator + cycle summary.

GORD-01..04 live + MORD-05 cycle summary against real Linear MCP. Behavior stubs
fail with the literal string "Wave 0 stub" (Nyquist enforcement). Filled in by
Plan 02 (Global Orchestrator) and Plan 04 (live MVP test).
"""

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_ready_tasks_returns_todo_only():
    """GORD-01 live: Returns only todo items from real Linear workspace."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 / verified live in Plan 04")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dependency_filter_against_live_linear():
    """GORD-02 live: Dependency filtering works against real Linear dependency graph."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 / verified live in Plan 04")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_backlog_signal_live():
    """GORD-03 live: is_backlog_empty=True against real Linear when empty."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 / verified live in Plan 04")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_epic_ready_signal_live():
    """GORD-04 live: is_epic_ready=True against real Linear when EPIC complete."""
    pytest.fail("Wave 0 stub — implemented in Plan 02 / verified live in Plan 04")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cycle_summary_posted():
    """MORD-05 live: Cycle summary is posted to Linear EPIC after run_main_orchestrator completes."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 / verified live in Plan 04")
