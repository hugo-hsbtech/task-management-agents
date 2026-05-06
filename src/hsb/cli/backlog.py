"""Backlog Agent CLI subcommands (populated by Phase 2 Plan 02).

Wave 0 scaffold: empty typer.Typer() instance under module attribute `app`.
Plan 02 adds @app.command(...) decorators here without touching cli/main.py.
"""
import typer
from rich.pretty import pprint

from hsb.agents.backlog_agent import run_backlog_agent
from hsb.contracts.backlog import BacklogInput, ProjectContext

app = typer.Typer(name="backlog", help="Backlog Planning Agent commands")


@app.callback()
def _backlog_callback() -> None:
    """Backlog Agent — read plan.md and create Linear hierarchy (BKPK-01..05)."""


@app.command("create")
def backlog_create(
    plan: str = typer.Option(..., "--plan", help="Absolute path to plan.md (D-02: required)"),
    project_name: str = typer.Option(..., "--project-name", help="Project name for traceability"),
    repository: str = typer.Option(..., "--repository", help="Repository URL"),
    stack: list[str] = typer.Option(
        None, "--stack", help="Repeatable: --stack python --stack typer"
    ),
):
    """Create Linear EPIC -> Story -> Task hierarchy from plan.md (BKPK-01..05)."""
    input = BacklogInput(
        plan_source=plan,
        project_context=ProjectContext(
            name=project_name,
            repository=repository,
            technical_stack=stack or [],
        ),
    )
    result = run_backlog_agent(input)
    pprint(result.model_dump())
