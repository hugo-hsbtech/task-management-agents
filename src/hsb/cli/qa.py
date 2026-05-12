"""QA Agent CLI subcommands (populated by Phase 2 Plan 05)."""

import asyncio
import subprocess

import typer
from rich.pretty import pprint

from hsb.agents.linear_agent import run_validated_linear_agent  # Phase 1 service
from hsb.agents.qa_agent import run_qa_agent
from hsb.contracts.qa import PullRequestInput, QAInput

app = typer.Typer(name="qa", help="QA Review Agent commands")


@app.callback()
def _qa_callback() -> None:
    """QA Agent — review PR diff against Linear issue (QAAG-01..05)."""


@app.command("review")
def qa_review(
    issue_id: str = typer.Option(
        ..., "--issue-id", help="Linear work item ID (e.g. LIN-123)"
    ),
    pr_number: int = typer.Option(
        ..., "--pr-number", help="GitHub PR number to review"
    ),
    qa_cycle: int = typer.Option(
        0,
        "--qa-cycle",
        help="Current QA cycle count (0-indexed: 0=first review, 1=second, 2=third)",
    ),
) -> None:
    """Review a PR diff against a Linear work item (QAAG-01..05).

    Pitfall 6 mitigation: fetches Linear issue and PR diff IMMEDIATELY before invoking
    the agent — never uses cached state.

    D-04: After QAOutput validates (model_validator enforces cycle cap),
    run_qa_agent automatically writes qa_cycle_count + fix subtasks to Linear via the
    Phase 1 Linear Agent service. The QA Agent itself has zero Linear MCP access.
    """
    if qa_cycle not in (0, 1, 2):
        raise typer.BadParameter(
            f"qa_cycle must be 0, 1, or 2 (0-indexed). Got {qa_cycle}. "
            f"At qa_cycle=2 the agent MUST approve with tech_debt_annotation (QAAG-04)."
        )

    # Fresh fetch — Pitfall 6
    diff = subprocess.check_output(["gh", "pr", "diff", str(pr_number)], text=True)
    pr_url = subprocess.check_output(
        ["gh", "pr", "view", str(pr_number), "--json", "url", "--jq", ".url"],
        text=True,
    ).strip()
    linear_result = asyncio.run(
        run_validated_linear_agent(operation="read", payload={"issueId": issue_id})
    )
    if not linear_result.linear_entities:
        raise typer.BadParameter(
            f"Linear Agent returned no entities for {issue_id}. Verify the issue exists."
        )

    input = QAInput(
        work_item_id=issue_id,
        linear_issue=linear_result.model_dump(),
        pull_request=PullRequestInput(url=pr_url, diff=diff),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=qa_cycle,
    )
    result = run_qa_agent(input)
    pprint(result.model_dump())
