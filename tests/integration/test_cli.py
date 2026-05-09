"""Plan 03-04 — Phase 3 CLI integration tests against real Linear.

Tests the operator-facing CLI (``hsb run-next-step``, ``hsb show-state``)
against the live Linear test workspace via Typer's ``CliRunner``. Each
test SKIPS gracefully when ``TEST_WORK_ITEM_ID`` is not set.

VALIDATION.md aliases:
- CLIR-01: ``test_run_next_step``
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from hsb.cli.main import app

pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _require_test_work_item_id() -> str:
    work_item_id = os.environ.get("TEST_WORK_ITEM_ID")
    if not work_item_id:
        pytest.skip(
            "TEST_WORK_ITEM_ID env var not set — set to a seeded Linear Task ID "
            "(see 03-04-PLAN.md Task 2 setup)."
        )
    return work_item_id


# --- CLIR-01: hsb run-next-step triggers one orchestration cycle ------------


@pytest.mark.integration
def test_run_next_step_triggers_lifecycle() -> None:
    """CLIR-01: ``hsb run-next-step`` triggers one orchestration cycle against real Linear."""
    work_item_id = _require_test_work_item_id()
    result = runner.invoke(app, ["run-next-step", "--work-item-id", work_item_id])
    assert result.exit_code == 0, (
        f"run-next-step failed: stdout={result.stdout!r} exception={result.exception!r}"
    )


@pytest.mark.integration
def test_run_next_step() -> None:
    """CLIR-01 alias matching VALIDATION.md command ID."""
    test_run_next_step_triggers_lifecycle()


# --- CLIR-02 (integration variant) ------------------------------------------


@pytest.mark.integration
def test_show_state_returns_table_output() -> None:
    """CLIR-02: ``hsb show-state`` produces a rich Table against real Linear state.

    No ``TEST_WORK_ITEM_ID`` is required — show-state is read-only and works
    against any non-empty Linear workspace. We assert the command exits 0 and
    that at least one D-08 column header (or the Table title) appears in the
    rendered output.
    """
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LINEAR_API_KEY")):
        pytest.skip(
            "Neither ANTHROPIC_API_KEY nor LINEAR_API_KEY set — show-state "
            "needs Linear MCP credentials."
        )
    result = runner.invoke(app, ["show-state"])
    assert result.exit_code == 0, (
        f"show-state failed: stdout={result.stdout!r} exception={result.exception!r}"
    )
    assert any(
        marker in result.stdout
        for marker in ("HSBTech Work Item State", "EPIC", "Task", "QA Status")
    ), f"show-state output missing Table markers: {result.stdout!r}"
