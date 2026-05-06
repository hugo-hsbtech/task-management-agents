"""Wave 0 / Plan 03-01 — CLI integration test stubs.

Plan 03-03 wires the Phase 3 Typer commands; Plan 03-04 converts these stubs
into live runs against the real Linear workspace + ``hsb-test-fixture`` repo.

VALIDATION.md aliases:
- CLIR-01: ``test_run_next_step``
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


# --- CLIR-01: hsb run-next-step triggers one orchestration cycle ------------

@pytest.mark.integration
def test_run_next_step_triggers_lifecycle() -> None:
    """CLIR-01: hsb run-next-step triggers one orchestration cycle against real Linear."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")


@pytest.mark.integration
def test_run_next_step() -> None:
    """CLIR-01 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")


# --- CLIR-02 (integration variant) ------------------------------------------

@pytest.mark.integration
def test_show_state_returns_table_output() -> None:
    """CLIR-02: hsb show-state produces a rich table against real Linear state."""
    pytest.fail("Wave 0 stub — implemented in Plan 04 (live MVP cycle)")
