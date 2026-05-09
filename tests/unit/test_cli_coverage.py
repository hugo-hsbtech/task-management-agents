"""CLI coverage tests for src/hsb/cli/.

Covers backlog, builder, git, qa, and uncovered branches in main.py.
Uses Typer's CliRunner with mocked agent calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hsb.contracts.backlog import (
    BacklogOutput,
    BacklogTraceability,
    EpicItem,
    TaskItem,
    UserStory,
)
from hsb.contracts.builder import (
    BuilderOutput,
    FileChanged,
    ImplementationNotes,
    ValidationResults,
)
from hsb.contracts.git import GitOutput, PullRequest
from hsb.contracts.linear import LinearEntity, LinearOutput
from hsb.contracts.qa import QAOutput


runner = CliRunner()


def _valid_linear_output() -> LinearOutput:
    return LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(
                id="LIN-100",
                type="task",
                url="https://linear.app/x/LIN-100",
            )
        ],
        error=None,
    )


def _valid_backlog_output(plan_path: str) -> BacklogOutput:
    return BacklogOutput(
        epics=[
            EpicItem(
                title="[EPIC] Test",
                description="d",
                user_stories=[
                    UserStory(
                        title="s",
                        description="d",
                        tasks=[TaskItem(title="t", description="d")],
                    )
                ],
            )
        ],
        traceability=BacklogTraceability(plan_source=plan_path),
    )


def _valid_builder_output() -> BuilderOutput:
    return BuilderOutput(
        work_item_id="LIN-100",
        implementation_status="completed",
        summary="ok",
        files_changed=[FileChanged(path="x.py", change_summary="x")],
        validation=ValidationResults(
            build="not_run", tests="passed", lint="passed", typecheck="passed"
        ),
        implementation_notes=ImplementationNotes(),
    )


def _valid_git_output() -> GitOutput:
    return GitOutput(
        work_item_id="LIN-100",
        branch="feature/LIN-100-x",
        commits=["abc"],
        pull_request=PullRequest(
            url="https://github.com/x/y/pull/1",
            title="[LIN-100] x",
            base="epic/LIN-99",
            head="feature/LIN-100-x",
        ),
    )


def _valid_qa_output() -> QAOutput:
    return QAOutput(
        work_item_id="LIN-100",
        qa_status="approved",
        qa_cycle_count=1,
        summary="LGTM",
        findings=[],
    )


# -------------------------------------------------------------------------- #
# cli/backlog.py                                                             #
# -------------------------------------------------------------------------- #


def test_backlog_create_invokes_agent(tmp_path: Path):
    from hsb.cli.backlog import app

    plan = tmp_path / "plan.md"
    plan.write_text("# plan", encoding="utf-8")
    output = _valid_backlog_output(str(plan))

    with patch("hsb.cli.backlog.run_backlog_agent", return_value=output) as mock:
        result = runner.invoke(
            app,
            [
                "create",
                "--plan", str(plan),
                "--project-name", "test",
                "--repository", "repo",
                "--stack", "python",
                "--stack", "typer",
            ],
        )
    assert result.exit_code == 0
    mock.assert_called_once()
    call_input = mock.call_args[0][0]
    assert call_input.plan_source == str(plan)
    assert call_input.project_context.technical_stack == ["python", "typer"]


def test_backlog_create_no_stack(tmp_path: Path):
    """--stack omitted should default to []."""
    from hsb.cli.backlog import app

    plan = tmp_path / "plan.md"
    plan.write_text("# plan", encoding="utf-8")
    output = _valid_backlog_output(str(plan))

    with patch("hsb.cli.backlog.run_backlog_agent", return_value=output):
        result = runner.invoke(
            app,
            [
                "create",
                "--plan", str(plan),
                "--project-name", "test",
                "--repository", "repo",
            ],
        )
    assert result.exit_code == 0


# -------------------------------------------------------------------------- #
# cli/builder.py                                                             #
# -------------------------------------------------------------------------- #


def test_builder_implement_invokes_agent(tmp_path: Path):
    from hsb.cli.builder import app

    linear_out = _valid_linear_output()
    builder_out = _valid_builder_output()

    with patch(
        "hsb.cli.builder.run_validated_linear_agent",
        new=AsyncMock(return_value=linear_out),
    ), patch(
        "hsb.cli.builder.run_builder_agent", return_value=builder_out
    ) as mock_builder:
        result = runner.invoke(
            app,
            [
                "implement",
                "--issue-id", "LIN-100",
                "--plan", "/p.md",
                "--repo-root", str(tmp_path),
                "--stack", "python",
            ],
        )
    assert result.exit_code == 0
    mock_builder.assert_called_once()


def test_builder_implement_no_entities_raises(tmp_path: Path):
    """When Linear returns empty, builder CLI raises BadParameter."""
    from hsb.cli.builder import app

    empty_linear = LinearOutput(
        operation="read", result="success", linear_entities=[], error=None
    )

    with patch(
        "hsb.cli.builder.run_validated_linear_agent",
        new=AsyncMock(return_value=empty_linear),
    ):
        result = runner.invoke(
            app,
            [
                "implement",
                "--issue-id", "LIN-100",
                "--plan", "/p.md",
                "--repo-root", str(tmp_path),
            ],
        )
    assert result.exit_code != 0  # BadParameter raises non-zero


# -------------------------------------------------------------------------- #
# cli/git.py                                                                 #
# -------------------------------------------------------------------------- #


def test_git_create_pr(tmp_path: Path):
    from hsb.cli.git import app

    impl_file = tmp_path / "impl.json"
    impl_file.write_text(json.dumps({"work_item_id": "LIN-100"}), encoding="utf-8")
    output = _valid_git_output()

    with patch("hsb.cli.git.run_git_agent", return_value=output) as mock:
        result = runner.invoke(
            app,
            [
                "create-pr",
                "--issue-id", "LIN-100",
                "--epic-id", "LIN-99",
                "--impl-output", str(impl_file),
            ],
        )
    assert result.exit_code == 0
    mock.assert_called_once()


def test_git_rebase_stack():
    from hsb.cli.git import app

    output = _valid_git_output()
    with patch("hsb.cli.git.run_git_agent", return_value=output) as mock:
        result = runner.invoke(
            app,
            [
                "rebase-stack",
                "--epic-branch", "epic/LIN-99",
                "--just-merged", "feature/LIN-100",
            ],
        )
    assert result.exit_code == 0
    mock.assert_called_once()
    call_input = mock.call_args[0][0]
    assert call_input.work_item_id.startswith("REBASE_STACK:")


# -------------------------------------------------------------------------- #
# cli/qa.py                                                                  #
# -------------------------------------------------------------------------- #


def test_qa_review_invalid_cycle():
    """qa_cycle outside 0-2 raises BadParameter."""
    from hsb.cli.qa import app

    result = runner.invoke(
        app,
        [
            "review",
            "--issue-id", "LIN-100",
            "--pr-number", "42",
            "--qa-cycle", "5",
        ],
    )
    assert result.exit_code != 0


def test_qa_review_no_linear_entities():
    """When Linear returns empty entities, qa CLI raises BadParameter."""
    from hsb.cli.qa import app

    empty_linear = LinearOutput(
        operation="read", result="success", linear_entities=[], error=None
    )

    with patch("hsb.cli.qa.subprocess.check_output", return_value="diff content"), \
         patch(
             "hsb.cli.qa.run_validated_linear_agent",
             new=AsyncMock(return_value=empty_linear),
         ):
        result = runner.invoke(
            app,
            [
                "review",
                "--issue-id", "LIN-100",
                "--pr-number", "42",
                "--qa-cycle", "0",
            ],
        )
    assert result.exit_code != 0


def test_qa_review_happy_path():
    from hsb.cli.qa import app

    linear_out = _valid_linear_output()
    qa_out = _valid_qa_output()

    with patch(
        "hsb.cli.qa.subprocess.check_output",
        side_effect=["diff content\n", "https://github.com/x/y/pull/42\n"],
    ), patch(
        "hsb.cli.qa.run_validated_linear_agent",
        new=AsyncMock(return_value=linear_out),
    ), patch(
        "hsb.cli.qa.run_qa_agent", return_value=qa_out
    ) as mock_qa:
        result = runner.invoke(
            app,
            [
                "review",
                "--issue-id", "LIN-100",
                "--pr-number", "42",
                "--qa-cycle", "1",
            ],
        )
    assert result.exit_code == 0
    mock_qa.assert_called_once()


# -------------------------------------------------------------------------- #
# cli/main.py — uncovered branches                                            #
# -------------------------------------------------------------------------- #


def test_main_dispatch_failure_exits_1():
    """_dispatch catches exceptions and exits with code 1."""
    from hsb.cli.main import app

    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = runner.invoke(
            app,
            [
                "create-issue",
                "--title", "x",
                "--team-id", "T-1",
            ],
        )
    assert result.exit_code == 1
    assert "Linear Agent failed" in result.output


def test_main_parse_epics_from_linear_output_with_epic():
    """_parse_epics_from_linear_output groups epics + tasks correctly."""
    from hsb.cli.main import _parse_epics_from_linear_output

    result = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-1", type="epic", url="https://linear.app/x/LIN-1"),
            LinearEntity(
                id="LIN-2",
                type="task",
                url="https://linear.app/x/LIN-2",
            ),
        ],
        error=None,
    )
    epics = _parse_epics_from_linear_output(result)
    assert len(epics) == 1
    assert len(epics[0]["tasks"]) == 1


def test_main_parse_epics_no_epic_synthesizes_group():
    """When no epics in entities, a synthetic '—' group is created."""
    from hsb.cli.main import _parse_epics_from_linear_output

    result = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-2", type="task", url="https://linear.app/x/LIN-2"),
        ],
        error=None,
    )
    epics = _parse_epics_from_linear_output(result)
    assert len(epics) == 1
    assert epics[0]["title"] == "—"


def test_main_show_state_runs():
    """show-state command renders a table from Linear state."""
    from hsb.cli.main import app

    linear_out = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-1", type="epic", url="https://linear.app/x/LIN-1"),
            LinearEntity(id="LIN-2", type="task", url="https://linear.app/x/LIN-2"),
        ],
        error=None,
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=linear_out),
    ):
        result = runner.invoke(app, ["show-state"])
    assert result.exit_code == 0


def test_main_show_state_empty_renders_dash_row():
    """show-state with empty entities renders a placeholder row."""
    from hsb.cli.main import app

    empty = LinearOutput(
        operation="read", result="success", linear_entities=[], error=None
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=empty),
    ):
        result = runner.invoke(app, ["show-state"])
    assert result.exit_code == 0


def test_main_show_next_action_qa_cycle_runaway():
    """qa_cycle_count >= 3 + changes_required → ESCALATE."""
    from hsb.cli.main import app

    out = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(
                id="LIN-1",
                type="task",
                url="https://linear.app/x/LIN-1",
            )
        ],
        error=None,
    )
    # Patch the linear_entities[0].model_dump() to include status fields
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=out),
    ), patch.object(
        LinearEntity,
        "model_dump",
        return_value={
            "id": "LIN-1",
            "qa_cycle_count": 3,
            "qa_status": "changes_required",
            "status": "in_progress",
        },
    ):
        result = runner.invoke(
            app, ["show-next-action", "--work-item-id", "LIN-1"]
        )
    assert result.exit_code == 0
    assert "ESCALATE" in result.output


def test_main_show_next_action_changes_required():
    """qa_status=changes_required → Builder Agent: address fix."""
    from hsb.cli.main import app

    out = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-1", type="task", url="https://linear.app/x/LIN-1")
        ],
        error=None,
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=out),
    ), patch.object(
        LinearEntity,
        "model_dump",
        return_value={
            "id": "LIN-1",
            "qa_status": "changes_required",
            "qa_cycle_count": 1,
        },
    ):
        result = runner.invoke(
            app, ["show-next-action", "--work-item-id", "LIN-1"]
        )
    assert result.exit_code == 0
    assert "Builder Agent" in result.output


def test_main_show_next_action_approved():
    """qa_status=approved → Git Agent ready."""
    from hsb.cli.main import app

    out = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-1", type="task", url="https://linear.app/x/LIN-1")
        ],
        error=None,
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=out),
    ), patch.object(
        LinearEntity,
        "model_dump",
        return_value={"id": "LIN-1", "qa_status": "approved"},
    ):
        result = runner.invoke(
            app, ["show-next-action", "--work-item-id", "LIN-1"]
        )
    assert result.exit_code == 0
    assert "Git Agent" in result.output


def test_main_show_next_action_fallback():
    """Status != todo and no qa_status → fallback message."""
    from hsb.cli.main import app

    out = LinearOutput(
        operation="read",
        result="success",
        linear_entities=[
            LinearEntity(id="LIN-1", type="task", url="https://linear.app/x/LIN-1")
        ],
        error=None,
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=out),
    ), patch.object(
        LinearEntity,
        "model_dump",
        return_value={
            "id": "LIN-1",
            "status": "in_progress",
            # qa_status absent → None → falls through to else
        },
    ):
        result = runner.invoke(
            app, ["show-next-action", "--work-item-id", "LIN-1"]
        )
    assert result.exit_code == 0
    assert "Read Linear state" in result.output


def test_main_show_next_action_no_target():
    """Empty linear_entities → fallback message."""
    from hsb.cli.main import app

    empty = LinearOutput(
        operation="read", result="success", linear_entities=[], error=None
    )
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=empty),
    ):
        result = runner.invoke(app, ["show-next-action"])
    assert result.exit_code == 0


def test_main_run_next_step():
    """run-next-step delegates to run_orchestration_cycle."""
    from hsb.cli.main import app

    with patch(
        "hsb.cli.main.run_orchestration_cycle", new=AsyncMock(return_value=None)
    ) as mock:
        result = runner.invoke(
            app, ["run-next-step", "--work-item-id", "LIN-1"]
        )
    assert result.exit_code == 0
    mock.assert_called_once()


def test_main_run_default_cascade_mode():
    """`hsb run` uses cascade by default."""
    from hsb.cli.main import app

    with patch(
        "hsb.cli.main.run_main_orchestrator", new=AsyncMock(return_value=None)
    ) as mock:
        result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert mock.call_args.kwargs.get("mode") == "cascade"


def test_main_run_parallel_mode():
    """`hsb run --parallel` uses parallel mode."""
    from hsb.cli.main import app

    with patch(
        "hsb.cli.main.run_main_orchestrator", new=AsyncMock(return_value=None)
    ) as mock:
        result = runner.invoke(app, ["run", "--parallel"])
    assert result.exit_code == 0
    assert mock.call_args.kwargs.get("mode") == "parallel"
