"""Plan 03-03 — Phase 3 CLI command unit tests.

Covers the three new Typer subcommands wired in Plan 03-03:
- ``run-next-step`` (CLIR-01)
- ``show-state`` (CLIR-02)
- ``show-next-action`` (CLIR-03)

VALIDATION.md command ID aliases mirror the canonical tests below.
"""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hsb.cli.main import app

runner = CliRunner()


def _stub_linear_output(entities: list | None = None) -> MagicMock:
    """Build a MagicMock that quacks like LinearOutput for the helper code."""
    mock = MagicMock()
    mock.linear_entities = entities or []
    mock.result = "success"
    return mock


# --- CLIR-02: show-state renders rich table without writes ------------------

def test_show_state_renders_table() -> None:
    """CLIR-02: hsb show-state renders a rich Table from Linear state. Read-only."""
    with patch(
        "hsb.cli.main.run_validated_linear_agent", new_callable=AsyncMock
    ) as mock_linear:
        mock_linear.return_value = _stub_linear_output([])
        result = runner.invoke(app, ["show-state"])
    assert result.exit_code == 0, result.output
    # Rich Table title or column header should appear in the rendered output
    assert (
        "HSBTech Work Item State" in result.output
        or "EPIC" in result.output
        or "Task" in result.output
    )


def test_show_state_renders() -> None:
    """CLIR-02 alias matching VALIDATION.md command ID."""
    test_show_state_renders_table()


# --- CLIR-03: show-next-action has no side effects --------------------------

def test_show_next_action_no_side_effects() -> None:
    """CLIR-03: show-next-action must produce output without any Linear writes."""
    with patch(
        "hsb.cli.main.run_validated_linear_agent", new_callable=AsyncMock
    ) as mock_linear:
        mock_linear.return_value = _stub_linear_output([])
        result = runner.invoke(app, ["show-next-action"])
    assert result.exit_code == 0, result.output
    # Every call must be a 'read' — never any write op
    for call in mock_linear.call_args_list:
        op = call.kwargs.get("operation") or (call.args[0] if call.args else None)
        assert op == "read", f"show-next-action triggered a write op: {op!r}"


# --- CLIR-05: No process-level state between invocations --------------------

def test_run_next_step_uses_asyncio_run() -> None:
    """CLIR-05: run-next-step handler must use asyncio.run() — not be async itself."""
    from hsb.cli.main import run_next_step

    assert not asyncio.iscoroutinefunction(run_next_step), (
        "run_next_step must be a synchronous Typer handler, not async. "
        "Wrap with asyncio.run() inside the function body."
    )
    source = inspect.getsource(run_next_step)
    assert "asyncio.run(" in source, (
        "run_next_step must call asyncio.run() to invoke run_orchestration_cycle()"
    )


def test_show_state_uses_asyncio_run() -> None:
    """CLIR-05: show-state handler must use asyncio.run()."""
    from hsb.cli.main import show_state

    assert not asyncio.iscoroutinefunction(show_state)
    source = inspect.getsource(show_state)
    assert "asyncio.run(" in source


def test_show_next_action_uses_asyncio_run() -> None:
    """CLIR-05: show-next-action handler must use asyncio.run()."""
    from hsb.cli.main import show_next_action

    assert not asyncio.iscoroutinefunction(show_next_action)
    source = inspect.getsource(show_next_action)
    assert "asyncio.run(" in source


def test_no_process_state() -> None:
    """CLIR-05: ``hsb.cli.main`` must not hold module-level *mutable* state
    beyond the Typer ``app`` instance itself and known read-only constants
    (e.g., the rich ``console``). The goal is no per-process MUTABLE state
    that handlers share across invocations.
    """
    import hsb.cli.main as m

    # Allowed mutable / shared singletons that are intentionally module-level
    allowed = {"app", "console", "backlog_app", "builder_app", "git_app", "qa_app"}
    bad = []
    for name, value in vars(m).items():
        if name.startswith("_"):
            continue
        if name in allowed:
            continue
        if isinstance(value, (dict, list, set)):
            bad.append(name)
    assert not bad, f"unexpected module-level mutable state in hsb.cli.main: {bad}"
