"""Wave 0 / Plan 03-01 — CLI unit test stubs.

These tests exercise the three Phase 3 Typer subcommands (``run-next-step``,
``show-state``, ``show-next-action``) added in Plan 03-03. Until that plan
ships, ``hsb.cli.main`` does not export those handlers — collection-time
imports are guarded so the suite stays parsable.

VALIDATION.md aliases:
- CLIR-02: ``test_show_state_renders``
- CLIR-03: ``test_show_next_action_no_side_effects``
- CLIR-05: ``test_no_process_state``
"""
from __future__ import annotations

import asyncio
import pytest
from typer.testing import CliRunner

try:
    from hsb.cli.main import app  # noqa: F401  (used after Plan 03-03 lands)
    _CLI_READY = True
except ImportError:  # pragma: no cover — Wave 0 protection
    _CLI_READY = False
    pytestmark = pytest.mark.skip(reason="Wave 0 stub: hsb.cli.main not yet extended")
else:
    pytestmark = []  # populated below if Phase 3 handlers are missing

runner = CliRunner()


def _phase3_handlers_present() -> bool:
    """Return True only if Plan 03-03 has wired the three Phase 3 commands."""
    try:
        from hsb.cli import main as cli_main
    except ImportError:  # pragma: no cover
        return False
    return all(
        hasattr(cli_main, attr)
        for attr in ("run_next_step", "show_state", "show_next_action")
    )


# --- CLIR-02: show-state renders rich table without writes ------------------

def test_show_state_renders_table() -> None:
    """CLIR-02: hsb show-state renders rich table from Linear state. Read-only."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")


def test_show_state_renders() -> None:
    """CLIR-02 alias matching VALIDATION.md command ID."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")


# --- CLIR-03: show-next-action has no side effects --------------------------

def test_show_next_action_no_side_effects() -> None:
    """CLIR-03: show-next-action must produce output without any Linear writes."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")


# --- CLIR-05: No process-level state between invocations --------------------

def test_run_next_step_uses_asyncio_run() -> None:
    """CLIR-05: run-next-step handler must use asyncio.run() — not be async itself."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")


def test_show_state_uses_asyncio_run() -> None:
    """CLIR-05: show-state handler must use asyncio.run()."""
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")


def test_no_process_state() -> None:
    """CLIR-05: ``hsb.cli.main`` must not hold module-level mutable state.

    VALIDATION.md command ID alias for the asyncio.run discipline above.
    """
    pytest.fail("Wave 0 stub — implemented in Plan 03 (hsb/cli/main.py extensions)")
