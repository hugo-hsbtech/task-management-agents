"""Wave 0 / Plan 03-01 — run_loop.py integration test stubs.

Plan 03-03 ships ``run_loop.py``; Plan 03-04 verifies its termination semantics
against the real Linear test workspace.

VALIDATION.md aliases:
- CLIR-04: ``test_loop_terminates``
- Pitfall 5: ``test_loop_stops_on_run_next_step_failure``
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


# --- CLIR-04: run_loop terminates when no ready tasks -----------------------

@pytest.mark.integration
def test_loop_terminates_when_no_ready_tasks() -> None:
    """CLIR-04: run_loop.py exits when no todo tasks remain in Linear."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")


@pytest.mark.integration
def test_loop_terminates() -> None:
    """CLIR-04 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")


# --- CLIR-04: graceful Ctrl+C handling --------------------------------------

@pytest.mark.integration
def test_loop_exits_on_ctrl_c() -> None:
    """CLIR-04: run_loop.py stops cleanly on KeyboardInterrupt."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")


# --- Pitfall 5: loop stops on non-zero exit ---------------------------------

@pytest.mark.integration
def test_loop_stops_on_run_next_step_failure() -> None:
    """RESEARCH.md Pitfall 5: loop stops when run-next-step exits non-zero."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")
