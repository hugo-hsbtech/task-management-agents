"""Builder Agent CLI subcommands (populated by Phase 2 Plan 03)."""
import typer

app = typer.Typer(name="builder", help="Builder Agent commands")


@app.callback()
def _builder_callback() -> None:
    """Builder Agent — implement a Linear work item locally (BLDR-01..04)."""
