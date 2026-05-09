"""TestModel-based unit tests for all PydanticAI agents.

Covers happy-path execution for backlog, builder, git, qa agents using
Agent.override(model=TestModel(...), toolsets=[]) so no real API or MCP
connections are needed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.models.test import TestModel

from hsb.contracts.backlog import (
    BacklogInput,
    BacklogOutput,
    BacklogTraceability,
    EpicItem,
    ProjectContext,
    TaskItem,
    UserStory,
)
from hsb.contracts.builder import (
    BuilderInput,
    BuilderOutput,
    FileChanged,
    ImplementationNotes,
    RepositoryContext,
    ValidationResults,
)
from hsb.contracts.git import GitInput, GitOutput, PullRequest
from hsb.contracts.qa import (
    PullRequestInput,
    QAInput,
    QAOutput,
)


# -------------------------------------------------------------------------- #
# Backlog Agent                                                              #
# -------------------------------------------------------------------------- #


def _valid_backlog_output(plan_path: str) -> BacklogOutput:
    return BacklogOutput(
        epics=[
            EpicItem(
                title="[EPIC] Test Epic",
                description="Plan excerpt",
                user_stories=[
                    UserStory(
                        title="Story 1",
                        description="excerpt",
                        tasks=[
                            TaskItem(title="Task 1", description="excerpt"),
                        ],
                    ),
                ],
            ),
        ],
        traceability=BacklogTraceability(plan_source=plan_path),
    )


@pytest.mark.asyncio
async def test_backlog_agent_happy_path(tmp_path: Path):
    """Backlog agent returns a valid BacklogOutput via TestModel."""
    from hsb.agents import backlog_agent as ba

    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nA simple plan", encoding="utf-8")
    output = _valid_backlog_output(str(plan))

    with ba._backlog_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await ba._run_backlog_agent_async(
            BacklogInput(
                project_context=ProjectContext(
                    name="test", repository="repo", technical_stack=["python"]
                ),
                plan_source=str(plan),
            )
        )
    assert isinstance(result, BacklogOutput)
    assert len(result.epics) == 1


def test_run_backlog_agent_sync_wrapper(tmp_path: Path):
    """The sync wrapper uses asyncio.run."""
    from hsb.agents import backlog_agent as ba

    plan = tmp_path / "plan.md"
    plan.write_text("# Plan", encoding="utf-8")
    output = _valid_backlog_output(str(plan))

    with ba._backlog_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = ba.run_backlog_agent(
            BacklogInput(
                project_context=ProjectContext(
                    name="test", repository="repo"
                ),
                plan_source=str(plan),
            )
        )
    assert isinstance(result, BacklogOutput)


# -------------------------------------------------------------------------- #
# Git Agent                                                                  #
# -------------------------------------------------------------------------- #


def _valid_git_output() -> GitOutput:
    return GitOutput(
        work_item_id="LIN-100",
        branch="feature/LIN-100-test",
        commits=["abc123"],
        pull_request=PullRequest(
            url="https://github.com/x/y/pull/1",
            title="[LIN-100] test",
            base="epic/LIN-99",
            head="feature/LIN-100-test",
        ),
    )


@pytest.mark.asyncio
async def test_git_agent_happy_path():
    from hsb.agents import git_agent as ga

    output = _valid_git_output()

    with ga._git_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await ga._run_git_agent_async(
            GitInput(
                work_item_id="LIN-100",
                implementation_output={"status": "ok"},
                epic_id="LIN-99",
            )
        )
    assert isinstance(result, GitOutput)
    assert result.branch == "feature/LIN-100-test"


def test_run_git_agent_sync_wrapper():
    from hsb.agents import git_agent as ga

    output = _valid_git_output()
    with ga._git_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = ga.run_git_agent(
            GitInput(
                work_item_id="LIN-100",
                implementation_output={"status": "ok"},
                epic_id="LIN-99",
            )
        )
    assert isinstance(result, GitOutput)


# -------------------------------------------------------------------------- #
# QA Agent                                                                   #
# -------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_qa_agent_happy_path(monkeypatch):
    """QA agent returns a valid QAOutput via TestModel.
    The Linear write side-effect is mocked out."""
    from hsb.agents import qa_agent as qa
    from unittest.mock import AsyncMock, MagicMock

    output = QAOutput(
        work_item_id="LIN-100",
        qa_status="approved",
        qa_cycle_count=1,
        summary="LGTM",
        findings=[],
    )

    with qa._qa_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await qa._run_qa_agent_async(
            QAInput(
                work_item_id="LIN-100",
                linear_issue={"id": "LIN-100"},
                pull_request=PullRequestInput(
                    url="https://github.com/x/y/pull/1",
                    diff="diff content",
                ),
                implementation_notes={},
                epic_context={},
                qa_cycle_count=0,
            )
        )
    assert isinstance(result, QAOutput)
    assert result.qa_status == "approved"


def test_run_qa_agent_sync_wrapper(monkeypatch):
    """The sync wrapper runs agent + writes results to Linear."""
    from hsb.agents import qa_agent as qa
    from unittest.mock import AsyncMock, MagicMock

    output = QAOutput(
        work_item_id="LIN-100",
        qa_status="approved",
        qa_cycle_count=1,
        summary="LGTM",
        findings=[],
    )

    # Mock the Linear write side-effect
    mock_linear = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(qa, "run_validated_linear_agent", mock_linear)

    with qa._qa_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = qa.run_qa_agent(
            QAInput(
                work_item_id="LIN-100",
                linear_issue={"id": "LIN-100"},
                pull_request=PullRequestInput(
                    url="https://github.com/x/y/pull/1",
                    diff="diff content",
                ),
                implementation_notes={},
                epic_context={},
                qa_cycle_count=0,
            )
        )
    assert isinstance(result, QAOutput)
    # Linear update was called
    mock_linear.assert_called()


# -------------------------------------------------------------------------- #
# Builder Agent                                                              #
# -------------------------------------------------------------------------- #


def _valid_builder_output() -> BuilderOutput:
    return BuilderOutput(
        work_item_id="LIN-100",
        implementation_status="completed",
        summary="Did the thing",
        files_changed=[
            FileChanged(path="src/foo.py", change_summary="added foo"),
        ],
        validation=ValidationResults(
            build="not_run",
            tests="passed",
            lint="passed",
            typecheck="passed",
        ),
        implementation_notes=ImplementationNotes(),
    )


@pytest.mark.asyncio
async def test_builder_agent_happy_path(tmp_path: Path):
    from hsb.agents import builder_agent as bld

    output = _valid_builder_output()

    with bld._builder_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await bld._run_builder_agent_async(
            BuilderInput(
                work_item_id="LIN-100",
                issue_description="implement X",
                acceptance_criteria=["AC-1: it works"],
                epic_context={"id": "LIN-99"},
                plan_source="/docs/plan.md",
                repository_context=RepositoryContext(root_path=str(tmp_path)),
            )
        )
    assert isinstance(result, BuilderOutput)


def test_run_builder_agent_sync_wrapper(tmp_path: Path):
    from hsb.agents import builder_agent as bld

    output = _valid_builder_output()

    with bld._builder_agent.override(
        model=TestModel(custom_output_args=output.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = bld.run_builder_agent(
            BuilderInput(
                work_item_id="LIN-100",
                issue_description="implement X",
                acceptance_criteria=["AC-1"],
                epic_context={},
                plan_source="/docs/plan.md",
                repository_context=RepositoryContext(root_path=str(tmp_path)),
            )
        )
    assert isinstance(result, BuilderOutput)


# -------------------------------------------------------------------------- #
# WIO assemble_system_prompt edge cases                                      #
# -------------------------------------------------------------------------- #


def test_wio_assemble_system_prompt_handles_missing_files(monkeypatch):
    """assemble_system_prompt logs a warning for missing skill files."""
    from hsb.agents import work_item_orchestrator as wio

    monkeypatch.setattr(
        wio, "SKILL_FILES", ["nonexistent/path1.md", "nonexistent/path2.md"]
    )
    result = wio.assemble_system_prompt()
    assert isinstance(result, str)


def test_wio_check_context_budget_handles_missing_usage():
    """_check_context_budget swallows AttributeErrors gracefully."""
    from hsb.agents import work_item_orchestrator as wio

    # Pass a result-like object that has no usage() method
    class FakeResult:
        pass

    # Should not raise
    wio._check_context_budget(FakeResult(), "LIN-1", "test")


def test_wio_check_context_budget_warns_at_threshold(caplog):
    """_check_context_budget logs a warning above 120K tokens."""
    from hsb.agents import work_item_orchestrator as wio

    class FakeUsage:
        input_tokens = 150_000

    class FakeResult:
        def usage(self):
            return FakeUsage()

    import logging

    with caplog.at_level(logging.WARNING):
        wio._check_context_budget(FakeResult(), "LIN-1", "test")
    assert any("WIO context" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_wio_qa_cycle_cap_silent_below_3():
    """_check_qa_cycle_cap is silent when cycle_count < 3."""
    from unittest.mock import AsyncMock

    from hsb.agents import work_item_orchestrator as wio

    mock_linear = AsyncMock()
    import unittest.mock

    with unittest.mock.patch(
        "hsb.agents.work_item_orchestrator.run_validated_linear_agent",
        new=mock_linear,
    ):
        await wio._check_qa_cycle_cap("LIN-1", qa_cycle_count=2, qa_status="changes_required")
    mock_linear.assert_not_called()
