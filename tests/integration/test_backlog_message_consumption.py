"""Coverage tests for backlog_agent.py message-consumption branches.

Covers:
  - lines 99-106: SystemMessage init with failed MCP → RuntimeError
  - lines 113-114: AssistantMessage block printing (text + name blocks)
  - line 122: ResultMessage with non-"success" subtype → RuntimeError
  - line 138-139: attempt leaves result_text=None (no ResultMessage) → continue
  - line 155: result_text=None after all messages consumed → logger.warning continue
  - line 162: exhausted retries with validation failure → ValueError

Uses spec-bound MagicMocks matching the pattern from test_backlog_runtime_parity.py.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage

from hsb.agents.backlog_agent import _run_backlog_agent_async
from hsb.contracts.backlog import BacklogInput, ProjectContext

# ---------------------------------------------------------------------------
# Minimal valid BacklogOutput JSON for happy-path assertions
# ---------------------------------------------------------------------------
FIXTURE_BACKLOG_JSON = json.dumps(
    {
        "epics": [
            {
                "title": "[EPIC] Test epic",
                "description": "> excerpt",
                "acceptance_criteria": [],
                "user_stories": [],
                "tasks": [],
            }
        ],
        "traceability": {"plan_source": "fixture/plan.md"},
    }
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def backlog_input(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\nA fixture plan.\n")
    return BacklogInput(
        plan_source=str(plan),
        project_context=ProjectContext(
            name="fixture",
            repository="https://github.com/example/fixture",
        ),
    )


def _make_result_message(*, subtype: str, result: str | None = None) -> MagicMock:
    """Build a spec-bound ResultMessage mock."""
    msg = MagicMock(spec=ResultMessage)
    msg.subtype = subtype
    msg.result = result
    msg.usage = {}
    return msg


def _make_assistant_message(blocks) -> MagicMock:
    """Build a spec-bound AssistantMessage mock with the given content blocks."""
    msg = MagicMock(spec=AssistantMessage)
    msg.content = blocks
    return msg


def _make_system_message(*, subtype: str, data: dict) -> MagicMock:
    """Build a spec-bound SystemMessage mock."""
    msg = MagicMock(spec=SystemMessage)
    msg.subtype = subtype
    msg.data = data
    return msg


# ---------------------------------------------------------------------------
# (a) SystemMessage init with failed MCP raises RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_init_with_failed_mcp_raises(
    monkeypatch, backlog_input
):
    """Lines 99-106: SystemMessage subtype='init' with a non-connected MCP server
    must raise RuntimeError matching 'Linear MCP failed'."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    sys_msg = _make_system_message(
        subtype="init",
        data={
            "mcp_servers": [
                {"name": "linear", "status": "failed"},
            ]
        },
    )

    async def fake_query(prompt, options):
        yield sys_msg

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        with pytest.raises(RuntimeError, match=r"Linear MCP failed"):
            await _run_backlog_agent_async(backlog_input)


# ---------------------------------------------------------------------------
# (b) AssistantMessage content blocks: both .text and .name paths print + continue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assistant_message_text_block_prints_and_continues(
    monkeypatch, backlog_input, capsys
):
    """Lines 113-114: AssistantMessage with a .text block and a .name block
    must print both and then allow a subsequent ResultMessage to produce output."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    # Block with .text attribute
    text_block = MagicMock()
    text_block.text = "planning output"
    # Ensure .name is NOT present so hasattr check falls through to else:
    del text_block.name

    # Block with .name attribute but no .text
    name_block = MagicMock()
    name_block.name = "mcp__linear__create_issue"
    del name_block.text

    assistant_msg = _make_assistant_message([text_block, name_block])

    result_msg = _make_result_message(subtype="success", result=FIXTURE_BACKLOG_JSON)

    async def fake_query(prompt, options):
        yield assistant_msg
        yield result_msg

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        out = await _run_backlog_agent_async(backlog_input)

    captured = capsys.readouterr()
    assert "planning output" in captured.out
    assert "[TOOL] mcp__linear__create_issue" in captured.out
    assert len(out.epics) == 1


# ---------------------------------------------------------------------------
# (c) ResultMessage with failure subtype raises RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_result_message_failure_subtype_raises(monkeypatch, backlog_input):
    """Line 122: ResultMessage with subtype != 'success' must raise RuntimeError
    matching 'Backlog Agent failed'."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    result_msg = _make_result_message(subtype="error_max_turns")

    async def fake_query(prompt, options):
        yield result_msg

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        with pytest.raises(RuntimeError, match=r"Backlog Agent failed"):
            await _run_backlog_agent_async(backlog_input)


# ---------------------------------------------------------------------------
# (d) No ResultMessage in stream → result_text stays None → retry succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_with_no_result_text_continues_to_next_retry(
    monkeypatch, backlog_input
):
    """Lines 138-139, 155: first attempt has only an AssistantMessage (no ResultMessage,
    no is_final Message) → result_text=None → logger.warning continue.
    Second attempt yields a good ResultMessage → success."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    # Block with only a .text attribute (no .name)
    text_block = MagicMock()
    text_block.text = "thinking..."
    del text_block.name

    assistant_msg = _make_assistant_message([text_block])
    good_result = _make_result_message(subtype="success", result=FIXTURE_BACKLOG_JSON)

    call_count = {"n": 0}

    async def fake_query(prompt, options):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First attempt: only an AssistantMessage, no ResultMessage at all.
            # result_text will remain None after the loop → hits line 138-139 continue.
            yield assistant_msg
        else:
            yield good_result

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        out = await _run_backlog_agent_async(backlog_input)

    assert call_count["n"] == 2
    assert len(out.epics) == 1


# ---------------------------------------------------------------------------
# (e) Exhausted retries with validation failure → ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_init_with_all_connected_continues(
    monkeypatch, backlog_input
):
    """Line 106: SystemMessage subtype='init' where ALL MCP servers are connected
    must hit the `continue` (not raise) and allow subsequent messages to succeed."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    sys_msg = _make_system_message(
        subtype="init",
        data={
            "mcp_servers": [
                {"name": "linear", "status": "connected"},
            ]
        },
    )
    result_msg = _make_result_message(subtype="success", result=FIXTURE_BACKLOG_JSON)

    async def fake_query(prompt, options):
        yield sys_msg
        yield result_msg

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        out = await _run_backlog_agent_async(backlog_input)

    assert len(out.epics) == 1


@pytest.mark.asyncio
async def test_raises_after_exhausted_retries_with_validation_failure(
    monkeypatch, backlog_input
):
    """Line 155+162: after MAX_VALIDATION_RETRIES attempts all yielding invalid JSON
    ResultMessages, must raise ValueError matching 'failed validation after 3 attempts'."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    # Each call yields a ResultMessage with a result that is not valid BacklogOutput JSON.
    bad_result = _make_result_message(subtype="success", result='{"invalid": true}')

    async def fake_query(prompt, options):
        yield bad_result

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        with pytest.raises(ValueError, match=r"failed validation after 3 attempts"):
            await _run_backlog_agent_async(backlog_input)


# ---------------------------------------------------------------------------
# (f) Synchronous entry point run_backlog_agent covers line 162
# ---------------------------------------------------------------------------


def test_run_backlog_agent_sync_wrapper_returns_valid_output(
    monkeypatch, backlog_input
):
    """Line 162: run_backlog_agent (sync wrapper) calls asyncio.run and returns BacklogOutput."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    from hsb.agents.backlog_agent import run_backlog_agent

    result_msg = _make_result_message(subtype="success", result=FIXTURE_BACKLOG_JSON)

    async def fake_query(prompt, options):
        yield result_msg

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        out = run_backlog_agent(backlog_input)

    assert len(out.epics) == 1
    assert out.epics[0].title == "[EPIC] Test epic"
