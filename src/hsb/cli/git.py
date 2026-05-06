"""Git Agent CLI subcommands (populated by Phase 2 Plan 04)."""
import typer

app = typer.Typer(name="git", help="Git/PR Management Agent commands")


@app.callback()
def _git_callback() -> None:
    """Git Agent — create branches and PRs for completed work items (GITA-01..05)."""
