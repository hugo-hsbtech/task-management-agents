"""Git Agent CLI subcommands (populated by Phase 2 Plan 04)."""
import json as _json
from pathlib import Path

import typer
from rich.pretty import pprint

from hsb.agents.git_agent import run_git_agent
from hsb.contracts.git import GitInput

app = typer.Typer(name="git", help="Git/PR Management Agent commands")


@app.callback()
def _git_callback() -> None:
    """Git Agent — create branches and PRs for completed work items (GITA-01..05)."""


@app.command("create-pr")
def git_create_pr(
    issue_id: str = typer.Option(..., "--issue-id", help="Linear work item ID (e.g. LIN-123)"),
    epic_id: str = typer.Option(..., "--epic-id", help="Parent EPIC ID (e.g. LIN-100)"),
    impl_output: str = typer.Option(..., "--impl-output", help="Path to BuilderOutput JSON"),
):
    """Create branch + PR for a Linear work item (GITA-01..03)."""
    impl_data = _json.loads(Path(impl_output).read_text())
    input = GitInput(
        work_item_id=issue_id,
        implementation_output=impl_data,
        epic_id=epic_id,
    )
    result = run_git_agent(input)
    pprint(result.model_dump())


@app.command("rebase-stack")
def git_rebase_stack(
    epic_branch: str = typer.Option(..., "--epic-branch", help="Epic branch (e.g. epic/LIN-100)"),
    just_merged: str = typer.Option(..., "--just-merged", help="Branch just merged (excluded)"),
):
    """Rebase all open sibling task PRs after a merge (GITA-04, D-08).

    Uses gh pr list --limit 100 (Pitfall 4) and git rebase --onto with
    --force-with-lease (Pitfall 3).
    """
    input = GitInput(
        work_item_id=f"REBASE_STACK:{just_merged}",
        implementation_output={"operation": "rebase_stack", "just_merged": just_merged},
        epic_id=epic_branch,
    )
    result = run_git_agent(input)
    pprint(result.model_dump())
