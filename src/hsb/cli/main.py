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
# Phase 3 imports — Work Item Orchestrator + rich Table for show-state
from rich.table import Table
from hsb.agents.work_item_orchestrator import run_orchestration_cycle

app = typer.Typer(name="hsb", help="HSBTech AI Engineering Workflow CLI")
console = Console()

# Phase 2: register per-agent typer apps (each implemented in its own module so
# Wave 1 plans modify only their own file — no cli/main.py contention).
from hsb.cli.backlog import app as backlog_app
from hsb.cli.builder import app as builder_app
from hsb.cli.git import app as git_app
from hsb.cli.qa import app as qa_app

app.add_typer(backlog_app, name="backlog")
app.add_typer(builder_app, name="builder")
app.add_typer(git_app, name="git")
app.add_typer(qa_app, name="qa")


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


# --------------------------------------------------------------------------- #
# Phase 3 — Work Item Orchestrator commands (CLIR-01..05)                     #
# --------------------------------------------------------------------------- #
#
# All three handlers are SYNCHRONOUS (def, not async def) — Typer does not
# support async handlers (RESEARCH.md Anti-Patterns). Each handler wraps the
# async work in asyncio.run(...) so every CLI invocation is a standalone
# event-loop instance with no process-level state shared between calls
# (CLIR-05 enforcement).


def _parse_epics_from_linear_output(result: LinearOutput) -> list[dict]:
    """Best-effort projection of LinearOutput → ``[{"title", "tasks": [...]}]``.

    The Phase 1 ``LinearOutput`` contract only guarantees ``linear_entities``
    items with ``id``, ``type``, ``url``. ``read`` payloads in this codebase
    can return richer dicts in ``linear_entities`` once the Linear MCP read
    schema is finalized; until then we group entities by ``type`` and treat
    EPICs as parents of every Task we receive in the same response. Show-state
    rendering tolerates missing fields by defaulting to ``"—"``.

    NOTE: exact LinearOutput.read shape is finalized during Plan 04 against
    the live workspace. See CONTEXT.md "Claude's Discretion".
    """
    epics: list[dict] = []
    tasks: list[dict] = []
    for ent in result.linear_entities:
        # LinearEntity is a pydantic model; coerce to dict for uniform access
        data = ent.model_dump() if hasattr(ent, "model_dump") else dict(ent)
        if data.get("type") == "epic":
            epics.append({"title": data.get("title", data.get("id", "—")), "tasks": []})
        else:
            tasks.append(data)
    if not epics:
        # No epics returned — render a single synthetic group so the table
        # still shows the tasks we did receive.
        epics = [{"title": "—", "tasks": tasks}]
    else:
        # Naive grouping: every non-epic task lands under the first epic.
        # Plan 04 will refine this with parent_id resolution.
        epics[0]["tasks"].extend(tasks)
    return epics


async def _render_state_table() -> None:
    """Fetch Linear state and render a rich Table. Read-only — no writes (CLIR-02)."""
    result = await run_validated_linear_agent("read", {"scope": "all_epics"})
    epics = _parse_epics_from_linear_output(result)

    table = Table(
        title="HSBTech Work Item State",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("EPIC", style="bold", no_wrap=True)
    table.add_column("Task")
    table.add_column("Status", justify="center")
    table.add_column("QA Status", justify="center")
    table.add_column("QA Cycles", justify="right")
    table.add_column("PR Link")
    for epic in epics:
        epic_title = epic.get("title", "—")
        rendered_at_least_one_row = False
        for task in epic.get("tasks", []):
            table.add_row(
                epic_title,
                task.get("title", task.get("id", "—")),
                task.get("status", "—"),
                task.get("qa_status", "—"),
                str(task.get("qa_cycle_count", 0)),
                task.get("pr_link", task.get("url", "—")),
            )
            rendered_at_least_one_row = True
        if not rendered_at_least_one_row:
            table.add_row(epic_title, "—", "—", "—", "0", "—")
    console.print(table)


async def _render_next_action(work_item_id: str | None) -> None:
    """Compute the next recommended lifecycle action from Linear state.

    READ-ONLY — must NOT call any Linear write operation (CLIR-03 / T-3-04).
    """
    payload: dict[str, object] = (
        {"issueId": work_item_id} if work_item_id else {"filter": {"status": {"eq": "todo"}}}
    )
    result = await run_validated_linear_agent("read", payload)

    # The actual state inspection logic lives below the Linear read so the
    # decision is sourced from data fetched THIS call (no caching, no
    # cross-call mutation — CLIR-05).
    target = next(iter(result.linear_entities), None)
    target_data = (
        target.model_dump()
        if (target is not None and hasattr(target, "model_dump"))
        else (dict(target) if target else {})
    )
    status = target_data.get("status", "todo")
    qa_status = target_data.get("qa_status")
    qa_cycle_count = int(target_data.get("qa_cycle_count", 0))
    target_id = target_data.get("id", work_item_id or "—")

    if qa_cycle_count >= 3 and qa_status == "changes_required":
        action = "ESCALATE TO HUMAN: max QA cycles reached"
    elif qa_status == "changes_required":
        action = "Builder Agent: address fix subtasks"
    elif qa_status == "approved":
        action = "Git Agent: ready to merge EPIC PR (manual)"
    elif status == "todo":
        action = "Builder Agent: implement scope"
    else:
        action = "Read Linear state to determine next step"

    console.print(f"Next action for {target_id}: {action}")


@app.command("run-next-step")
def run_next_step(
    work_item_id: str = typer.Option(
        None,
        "--work-item-id",
        help="Linear work item ID (e.g. LIN-42). If omitted, selects next todo task automatically.",
    ),
) -> None:
    """Trigger one orchestration cycle — a single work item progresses exactly one lifecycle step (CLIR-01)."""
    # asyncio.run() at the CLI boundary only — NEVER inside a coroutine
    # (Phase 1 Shared Patterns; RESEARCH.md Anti-Patterns).
    asyncio.run(run_orchestration_cycle(work_item_id))


@app.command("show-state")
def show_state() -> None:
    """Render current system state: EPICs, tasks, QA status, PR links (CLIR-02, D-08)."""
    asyncio.run(_render_state_table())


@app.command("show-next-action")
def show_next_action(
    work_item_id: str = typer.Option(
        None,
        "--work-item-id",
        help="Linear work item ID. If omitted, inspects next available todo task.",
    ),
) -> None:
    """Display next recommended action without executing it (CLIR-03). No side effects."""
    asyncio.run(_render_next_action(work_item_id))


@app.callback()
def main() -> None:
    """HSBTech AI Engineering Workflow CLI."""


if __name__ == "__main__":
    app()
