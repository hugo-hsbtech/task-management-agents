"""Typer CLI for the HSBTech AI Engineering Workflow.

Each command delegates to run_validated_linear_agent (the pydantic-validated
entry point) via asyncio.run() at the CLI boundary. Typer is synchronous —
asyncio.run() is safe here. NEVER nest asyncio.run() inside an async function.
"""
from __future__ import annotations
import asyncio
import sys

import typer
from rich.console import Console
from rich.pretty import pprint

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.linear import LinearOutput

app = typer.Typer(name="hsb", help="HSBTech AI Engineering Workflow CLI")
console = Console()


def _dispatch(operation: str, payload: dict) -> LinearOutput:
    """Run validated agent and render the LinearOutput. Exit 1 on failure."""
    try:
        result = asyncio.run(run_validated_linear_agent(operation=operation, payload=payload))
    except Exception as exc:
        console.print(f"[red]Linear Agent failed:[/red] {exc}")
        raise typer.Exit(code=1)
    pprint(result.model_dump())
    return result


@app.command("create-issue")
def create_issue(
    title: str = typer.Option(..., "--title", help="Issue title"),
    type: str = typer.Option("task", "--type", help="epic | user_story | task | subtask"),
    team_id: str = typer.Option(..., "--team-id", help="Linear team ID"),
    parent_id: str | None = typer.Option(None, "--parent-id", help="Linear parent issue ID (required for non-epic)"),
    description: str | None = typer.Option(None, "--description", help="Issue description"),
) -> None:
    """Create a Linear issue with correct parent linkage (LINR-01)."""
    payload = {
        "title": title,
        "type": type,
        "teamId": team_id,
        "parentId": parent_id,
        "description": description,
    }
    _dispatch("create", payload)


@app.command("update-issue")
def update_issue(
    issue_id: str = typer.Option(..., "--issue-id", help="Linear issue ID (e.g. LIN-123)"),
    status: str | None = typer.Option(None, "--status", help="New workflow status (e.g. todo, in_progress, done)"),
    qa_status: str | None = typer.Option(None, "--qa-status", help="qa_status field (approved | changes_required)"),
    uat_status: str | None = typer.Option(None, "--uat-status", help="uat_status field (approved | changes_required)"),
    assigned_orchestrator: str | None = typer.Option(None, "--assigned-orchestrator", help="assigned_orchestrator field"),
) -> None:
    """Update a Linear issue's status, qa_status, uat_status, or assigned_orchestrator (LINR-02).

    Implementation note: status maps to Linear's standard workflow state. The other three
    fields are handled per LINR-02 — qa_status / uat_status / assigned_orchestrator may be
    implemented as Linear labels, custom fields, or structured comments depending on the
    workspace configuration. The Linear Agent system prompt instructs the model to inspect
    the MCP tool schema at runtime (RESEARCH.md Open Question 1).
    """
    payload = {
        "issueId": issue_id,
        "status": status,
        "qa_status": qa_status,
        "uat_status": uat_status,
        "assigned_orchestrator": assigned_orchestrator,
    }
    # Drop None values so the agent gets a clean payload
    payload = {k: v for k, v in payload.items() if v is not None}
    _dispatch("update", payload)


@app.command("add-comment")
def add_comment(
    issue_id: str = typer.Option(..., "--issue-id"),
    body: str = typer.Option(..., "--body", help="Comment body (markdown supported)"),
) -> None:
    """Add a structured comment to a Linear issue (LINR-03)."""
    payload = {"issueId": issue_id, "body": body}
    _dispatch("comment", payload)


@app.command("link-pr")
def link_pr(
    issue_id: str = typer.Option(..., "--issue-id"),
    pr_url: str = typer.Option(..., "--pr-url", help="GitHub PR URL"),
) -> None:
    """Link a GitHub PR URL to a Linear work item (LINR-04)."""
    payload = {"issueId": issue_id, "prUrl": pr_url}
    _dispatch("link", payload)


@app.callback()
def main() -> None:
    """HSBTech AI Engineering Workflow CLI."""


if __name__ == "__main__":
    app()
