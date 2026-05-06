"""Builder Agent CLI subcommands (populated by Phase 2 Plan 03)."""
import asyncio
import typer
from rich.pretty import pprint

from hsb.agents.builder_agent import run_builder_agent
from hsb.agents.linear_agent import run_validated_linear_agent  # Phase 1 service
from hsb.contracts.builder import BuilderInput, RepositoryContext

app = typer.Typer(name="builder", help="Builder Agent commands")


@app.callback()
def _builder_callback() -> None:
    """Builder Agent — implement a Linear work item locally (BLDR-01..04)."""


@app.command("implement")
def builder_implement(
    issue_id: str = typer.Option(..., "--issue-id", help="Linear work item ID (e.g. LIN-123)"),
    plan: str = typer.Option(..., "--plan", help="Path to plan.md that generated the issue"),
    repo_root: str = typer.Option(".", "--repo-root", help="Repository root for the implementation"),
    stack: list[str] = typer.Option(None, "--stack", help="Repeatable: --stack python --stack typer"),
):
    """Implement a Linear work item locally (BLDR-01..04).

    Pitfall 6 mitigation: ALWAYS fetch fresh Linear state immediately before
    constructing BuilderInput — never use cached issue content.
    """
    # Fresh Linear fetch (Pitfall 6)
    linear_result = asyncio.run(
        run_validated_linear_agent(operation="read", payload={"issueId": issue_id})
    )
    if not linear_result.linear_entities:
        raise typer.BadParameter(
            f"Linear Agent returned no entities for {issue_id}. "
            f"Verify the issue exists and the Linear MCP is authenticated."
        )
    issue_summary = str(linear_result.model_dump())

    input = BuilderInput(
        work_item_id=issue_id,
        issue_description=issue_summary,
        acceptance_criteria=[],
        epic_context={},
        plan_source=plan,
        repository_context=RepositoryContext(
            root_path=repo_root, technical_stack=stack or []
        ),
    )
    result = run_builder_agent(input)
    pprint(result.model_dump())
