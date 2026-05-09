"""Targeted tests filling specific coverage gaps.

Covers:
- Builder agent's inner @tool functions (read_file, write_file, edit_file,
  run_pytest, run_ruff, run_mypy)
- UAT agent's run_uat_and_validate
- WIO's tool dispatch wrappers (run_linear_op, run_builder, run_git, run_qa)
- guards.linear_write_guard sync wrapper
- qa_agent.run_qa_agent with findings (Linear subtask creation path)
- risk_agent edge cases (parse failures, top-level main block)
- linear_middleware.write_audit_entry directory creation
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel


# -------------------------------------------------------------------------- #
# Builder Agent inner tools                                                  #
# -------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_builder_read_file_resolves_relative_to_cwd(tmp_path: Path):
    from hsb.agents import builder_agent as bld
    from hsb.agents.builder_agent import BuilderDeps, read_file

    f = tmp_path / "x.txt"
    f.write_text("hello")

    ctx: RunContext[BuilderDeps] = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))
    result = await read_file(ctx, "x.txt")
    assert result == "hello"


@pytest.mark.asyncio
async def test_builder_read_file_handles_absolute(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, read_file

    f = tmp_path / "abs.txt"
    f.write_text("absolute")

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd="/different/path")
    result = await read_file(ctx, str(f))
    assert result == "absolute"


@pytest.mark.asyncio
async def test_builder_write_file_creates_parents(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, write_file

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    msg = await write_file(ctx, "deep/nested/x.txt", "data")
    assert (tmp_path / "deep" / "nested" / "x.txt").read_text() == "data"
    assert "Wrote" in msg


@pytest.mark.asyncio
async def test_builder_write_file_absolute_path(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, write_file

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd="/tmp")
    f = tmp_path / "abs.txt"
    msg = await write_file(ctx, str(f), "absolute write")
    assert f.read_text() == "absolute write"


@pytest.mark.asyncio
async def test_builder_edit_file_first_occurrence_only(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, edit_file

    f = tmp_path / "x.txt"
    f.write_text("foo bar foo")

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    msg = await edit_file(ctx, "x.txt", "foo", "qux")
    assert f.read_text() == "qux bar foo"
    assert "Edited" in msg


@pytest.mark.asyncio
async def test_builder_edit_file_no_match(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, edit_file

    f = tmp_path / "x.txt"
    f.write_text("hello")

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    msg = await edit_file(ctx, "x.txt", "absent", "qux")
    assert "No match" in msg


@pytest.mark.asyncio
async def test_builder_run_pytest_subprocess(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, run_pytest

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b""))
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await run_pytest(ctx, "-x")
    assert "out" in result


@pytest.mark.asyncio
async def test_builder_run_pytest_no_args(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, run_pytest

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"out", b""))
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await run_pytest(ctx)
    assert "out" in result


@pytest.mark.asyncio
async def test_builder_run_ruff(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, run_ruff

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"clean", b""))
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await run_ruff(ctx)
    assert "clean" in result


@pytest.mark.asyncio
async def test_builder_run_mypy(tmp_path: Path):
    from hsb.agents.builder_agent import BuilderDeps, run_mypy

    ctx = MagicMock()
    ctx.deps = BuilderDeps(cwd=str(tmp_path))

    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"ok", b""))
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = await run_mypy(ctx)
    assert "ok" in result


# -------------------------------------------------------------------------- #
# UAT Agent run_uat_and_validate                                              #
# -------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_uat_run_uat_and_validate(monkeypatch, tmp_path: Path):
    """run_uat_and_validate creates per-call agent and runs it."""
    from hsb.agents import uat_agent as ua
    from hsb.contracts.uat import UATResult, UATScenario

    monkeypatch.setattr(ua, "load_skill", lambda path: "skill content")

    output = UATResult(
        user_story_id="LIN-50",
        uat_cycle=1,
        overall_status="approved",
        scenarios=[
            UATScenario(
                criterion_id="AC-1",
                criterion_text="must work",
                status="pass",
                evidence="observable evidence here",
            )
        ],
    )

    # Patch Agent to use TestModel
    from pydantic_ai import Agent

    real_init = Agent.__init__

    def patched_init(self, *args, **kwargs):
        # Drop tools/toolsets for the test
        kwargs["tools"] = []
        kwargs["toolsets"] = []
        kwargs["model"] = TestModel(
            custom_output_args=output.model_dump(), call_tools=[]
        )
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(Agent, "__init__", patched_init)

    result = await ua.run_uat_and_validate(
        user_story_id="LIN-50",
        acceptance_criteria=["AC-1: must work"],
        uat_cycle=1,
    )
    assert isinstance(result, UATResult)


# -------------------------------------------------------------------------- #
# WIO tool wrappers                                                          #
# -------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_wio_run_linear_op_delegates(monkeypatch):
    """run_linear_op delegates to run_validated_linear_agent."""
    from hsb.agents import work_item_orchestrator as wio
    from hsb.contracts.linear import LinearOutput

    output = LinearOutput(
        operation="read", result="success", linear_entities=[], error=None
    )
    mock = AsyncMock(return_value=output)
    monkeypatch.setattr(wio, "run_validated_linear_agent", mock)

    result = await wio.run_linear_op(operation="read", payload={"id": "X"})
    mock.assert_called_once()
    parsed = json.loads(result)
    assert parsed["result"] == "success"


@pytest.mark.asyncio
async def test_wio_run_builder_dispatches(monkeypatch):
    """run_builder constructs BuilderInput and calls run_builder_agent."""
    from hsb.agents import work_item_orchestrator as wio
    from hsb.contracts.builder import BuilderOutput, FileChanged, ImplementationNotes, ValidationResults

    output = BuilderOutput(
        work_item_id="LIN-1",
        implementation_status="completed",
        summary="ok",
        files_changed=[FileChanged(path="x.py", change_summary="x")],
        validation=ValidationResults(
            build="not_run", tests="passed", lint="passed", typecheck="passed"
        ),
        implementation_notes=ImplementationNotes(),
    )
    mock = MagicMock(return_value=output)
    monkeypatch.setattr("hsb.agents.builder_agent.run_builder_agent", mock)

    issue_content = json.dumps({
        "description": "x",
        "acceptance_criteria": ["AC-1"],
        "epic_context": {},
        "plan_source": "/p",
        "root_path": "/repo",
    })
    result = await wio.run_builder(work_item_id="LIN-1", issue_content=issue_content)
    mock.assert_called_once()
    parsed = json.loads(result)
    assert parsed["work_item_id"] == "LIN-1"


@pytest.mark.asyncio
async def test_wio_run_git_dispatches(monkeypatch):
    """run_git constructs GitInput and calls run_git_agent."""
    from hsb.agents import work_item_orchestrator as wio
    from hsb.contracts.git import GitOutput, PullRequest

    output = GitOutput(
        work_item_id="LIN-1",
        branch="feature/LIN-1-test",
        commits=[],
        pull_request=PullRequest(
            url="u", title="t", base="epic/x", head="feature/LIN-1"
        ),
    )
    mock = MagicMock(return_value=output)
    monkeypatch.setattr("hsb.agents.git_agent.run_git_agent", mock)

    impl = json.dumps({"status": "ok"})
    result = await wio.run_git(
        work_item_id="LIN-1", impl_output=impl, epic_id="LIN-99"
    )
    mock.assert_called_once()
    assert "LIN-1" in result


@pytest.mark.asyncio
async def test_wio_run_qa_dispatches(monkeypatch):
    """run_qa constructs QAInput and calls run_qa_agent."""
    from hsb.agents import work_item_orchestrator as wio
    from hsb.contracts.qa import QAOutput

    output = QAOutput(
        work_item_id="LIN-1",
        qa_status="approved",
        qa_cycle_count=1,
        summary="LGTM",
        findings=[],
    )
    mock = MagicMock(return_value=output)
    monkeypatch.setattr("hsb.agents.qa_agent.run_qa_agent", mock)

    result = await wio.run_qa(
        work_item_id="LIN-1",
        pr_url="https://github.com/x/y/pull/1",
        diff="diff",
        qa_cycle_count=0,
    )
    mock.assert_called_once()
    assert "LIN-1" in result


# -------------------------------------------------------------------------- #
# guards.linear_write_guard sync wrapper                                     #
# -------------------------------------------------------------------------- #


def test_linear_write_guard_sync_wrapper():
    """The decorator returns a sync wrapper for sync functions."""
    from hsb.agents.guards import linear_write_guard

    @linear_write_guard
    def sync_write(payload):
        return f"wrote {payload}"

    result = sync_write({"id": "X"})
    assert result == "wrote {'id': 'X'}"


# -------------------------------------------------------------------------- #
# QA Agent _write_qa_results_to_linear with blocking findings                #
# -------------------------------------------------------------------------- #


def test_qa_writes_subtasks_for_blocking_findings(monkeypatch):
    """When findings have status='blocking' and qa_status='changes_required',
    _write_qa_results_to_linear creates subtasks via Linear."""
    from hsb.agents import qa_agent as qa
    from hsb.contracts.qa import (
        QAEvidence,
        QAFinding,
        QAOutput,
        SuggestedSubtask,
    )

    output = QAOutput(
        work_item_id="LIN-1",
        qa_status="changes_required",
        qa_cycle_count=1,
        summary="Issues found",
        findings=[
            QAFinding(
                title="Bug found",
                severity="critical",
                category="functional",
                status="blocking",
                problem="bad logic",
                evidence=QAEvidence(
                    file="x.py", component="foo", location="L1", related_requirement="AC-1"
                ),
                expected_behavior="works",
                actual_behavior="broken",
                suggested_fix="fix it",
                suggested_subtask=SuggestedSubtask(
                    title="[FIX] Fix bug",
                    description="Fix it",
                ),
            )
        ],
    )

    calls = []

    async def fake_linear(operation, payload):
        calls.append((operation, payload))
        return MagicMock()

    monkeypatch.setattr(qa, "run_validated_linear_agent", fake_linear)
    qa._write_qa_results_to_linear("LIN-1", output)
    # Should be 2 calls: 1 update + 1 create_subtasks
    assert len(calls) == 2
    operations = [c[0] for c in calls]
    assert "update" in operations
    assert "create_subtasks" in operations


def test_qa_no_subtasks_when_approved(monkeypatch):
    """When qa_status='approved', no subtasks are created."""
    from hsb.agents import qa_agent as qa
    from hsb.contracts.qa import QAOutput

    output = QAOutput(
        work_item_id="LIN-1",
        qa_status="approved",
        qa_cycle_count=1,
        summary="LGTM",
        findings=[],
    )

    calls = []

    async def fake_linear(operation, payload):
        calls.append((operation, payload))
        return MagicMock()

    monkeypatch.setattr(qa, "run_validated_linear_agent", fake_linear)
    qa._write_qa_results_to_linear("LIN-1", output)
    operations = [c[0] for c in calls]
    assert "create_subtasks" not in operations


# -------------------------------------------------------------------------- #
# Risk Agent edge cases                                                      #
# -------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_risk_agent_handles_invalid_json(monkeypatch):
    """detect_improvement_triggers gracefully handles invalid JSON output."""
    from hsb.agents import risk_agent as ra

    with ra._risk_agent.override(
        model=TestModel(custom_output_text="not valid json {", call_tools=[])
    ):
        agent = ra.RiskAgent()
        result = await agent.detect_improvement_triggers(qa_history=[], scores=[])
    assert result == []  # Empty list on parse failure


@pytest.mark.asyncio
async def test_risk_agent_handles_non_list_json(monkeypatch):
    """When LLM returns a JSON object instead of array, return empty list."""
    from hsb.agents import risk_agent as ra

    with ra._risk_agent.override(
        model=TestModel(custom_output_text='{"foo": "bar"}', call_tools=[])
    ):
        agent = ra.RiskAgent()
        result = await agent.detect_improvement_triggers(qa_history=[], scores=[])
    assert result == []


def test_risk_agent_load_skill_tool(tmp_path: Path):
    """load_skill reads a file and returns its contents."""
    from hsb.agents.risk_agent import load_skill

    f = tmp_path / "skill.md"
    f.write_text("skill body", encoding="utf-8")
    assert load_skill(str(f)) == "skill body"


# -------------------------------------------------------------------------- #
# linear_middleware coverage                                                 #
# -------------------------------------------------------------------------- #


def test_write_audit_entry_creates_dir_if_missing(tmp_path, monkeypatch):
    """write_audit_entry creates the parent directory if missing."""
    from hsb.agents import linear_middleware as lm

    log_path = tmp_path / "missing_dir" / "audit.log"
    monkeypatch.setattr(lm, "AUDIT_LOG_PATH", str(log_path))

    lm.write_audit_entry("tool", "tu_1", "preview")
    assert log_path.exists()
    assert log_path.parent.exists()
