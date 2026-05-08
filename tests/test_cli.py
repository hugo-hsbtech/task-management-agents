"""Smoke tests for typer CLI commands. No live MCP — mocks run_validated_linear_agent."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from hsb.cli.main import app
from hsb.contracts.linear import LinearOutput

runner = CliRunner()


def _success_output(operation: str = "create") -> LinearOutput:
    return LinearOutput.model_validate(
        {
            "operation": operation,
            "result": "success",
            "linear_entities": [
                {
                    "id": "LIN-1",
                    "type": "task",
                    "url": "https://linear.app/x/LIN-1",
                }
            ],
            "error": None,
        }
    )


def test_create_issue_dispatches():
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=_success_output("create")),
    ) as mock_agent:
        result = runner.invoke(
            app,
            [
                "create-issue",
                "--title",
                "test",
                "--type",
                "task",
                "--team-id",
                "T-1",
                "--parent-id",
                "LIN-99",
            ],
        )
    assert result.exit_code == 0
    mock_agent.assert_awaited_once()
    kwargs = mock_agent.call_args.kwargs
    assert kwargs["operation"] == "create"
    assert kwargs["payload"]["title"] == "test"
    assert kwargs["payload"]["teamId"] == "T-1"
    assert kwargs["payload"]["parentId"] == "LIN-99"


def test_update_issue_strips_none_values():
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=_success_output("update")),
    ) as mock_agent:
        result = runner.invoke(
            app,
            [
                "update-issue",
                "--issue-id",
                "LIN-1",
                "--status",
                "done",
            ],
        )
    assert result.exit_code == 0
    kwargs = mock_agent.call_args.kwargs
    assert kwargs["payload"] == {"issueId": "LIN-1", "status": "done"}
    # qa_status / uat_status / assigned_orchestrator should be absent (None values dropped)
    assert "qa_status" not in kwargs["payload"]


def test_add_comment_dispatches():
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=_success_output("comment")),
    ) as mock_agent:
        result = runner.invoke(
            app,
            [
                "add-comment",
                "--issue-id",
                "LIN-1",
                "--body",
                "test note",
            ],
        )
    assert result.exit_code == 0
    assert mock_agent.call_args.kwargs["operation"] == "comment"
    assert mock_agent.call_args.kwargs["payload"]["body"] == "test note"


def test_link_pr_dispatches():
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(return_value=_success_output("link")),
    ) as mock_agent:
        result = runner.invoke(
            app,
            [
                "link-pr",
                "--issue-id",
                "LIN-1",
                "--pr-url",
                "https://github.com/o/r/pull/1",
            ],
        )
    assert result.exit_code == 0
    assert mock_agent.call_args.kwargs["operation"] == "link"
    assert (
        mock_agent.call_args.kwargs["payload"]["prUrl"]
        == "https://github.com/o/r/pull/1"
    )


def test_create_issue_exits_1_on_agent_failure():
    with patch(
        "hsb.cli.main.run_validated_linear_agent",
        new=AsyncMock(side_effect=ValueError("simulated")),
    ):
        result = runner.invoke(
            app,
            [
                "create-issue",
                "--title",
                "x",
                "--type",
                "task",
                "--team-id",
                "T-1",
            ],
        )
    assert result.exit_code == 1
