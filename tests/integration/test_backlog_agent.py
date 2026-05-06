"""Integration tests for Backlog Agent — real Linear test workspace (D-09).

Wave 0 scaffold. Wave 1 Plan 02 implements the bodies. Function names match
02-VALIDATION.md commands exactly — DO NOT rename.

Covers: BKPK-01, BKPK-02, BKPK-03, BKPK-04, BKPK-05.

Run with: pytest tests/integration/ -v -m integration
Default `pytest tests/unit/` does NOT run these (deselected by marker).
"""
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
def test_parse_plan(tmp_path):
    """BKPK-01: Backlog Agent parses plan.md and produces a structured BacklogOutput."""
    pytest.skip("Wave 1 Plan 02 (Backlog Agent) implements this test body")


@pytest.mark.integration
def test_create_epics(tmp_path):
    """BKPK-02: every EPIC is persisted to Linear with title and traceability quote."""
    pytest.skip("Wave 1 Plan 02 (Backlog Agent) implements this test body")


@pytest.mark.integration
def test_create_user_stories(tmp_path):
    """BKPK-03: every User Story is persisted as a child of its EPIC."""
    pytest.skip("Wave 1 Plan 02 (Backlog Agent) implements this test body")


@pytest.mark.integration
def test_create_tasks(tmp_path):
    """BKPK-04: every Task is persisted as a child of a User Story or EPIC."""
    pytest.skip("Wave 1 Plan 02 (Backlog Agent) implements this test body")


@pytest.mark.integration
def test_idempotency(tmp_path):
    """BKPK-05 (Pitfall 1): running Backlog Agent twice on the same plan does NOT
    create duplicate EPICs in the Linear workspace.
    """
    pytest.skip("Wave 1 Plan 02 (Backlog Agent) implements this test body")
