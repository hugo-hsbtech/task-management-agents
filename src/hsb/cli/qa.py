"""QA Agent CLI subcommands (populated by Phase 2 Plan 05)."""
import typer

app = typer.Typer(name="qa", help="QA Review Agent commands")


@app.callback()
def _qa_callback() -> None:
    """QA Agent — review PR diff against Linear issue (QAAG-01..05)."""
