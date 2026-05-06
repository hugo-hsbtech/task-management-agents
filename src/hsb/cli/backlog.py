"""Backlog Agent CLI subcommands (populated by Phase 2 Plan 02).

Wave 0 scaffold: empty typer.Typer() instance under module attribute `app`.
Plan 02 adds @app.command(...) decorators here without touching cli/main.py.
"""
import typer

app = typer.Typer(name="backlog", help="Backlog Planning Agent commands")


@app.callback()
def _backlog_callback() -> None:
    """Backlog Agent — read plan.md and create Linear hierarchy (BKPK-01..05)."""
