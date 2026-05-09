"""G1/G2/G3 enforcement at the ``_sdk_options`` chokepoint.

Tests in this module deliberately use ``monkeypatch.setenv`` for the API-key
flow so the session-scoped autouse fixture in ``conftest.py`` is honored
(and restored) per-test.
"""

import os

import pytest

from hsb.agents._sdk_options import (
    assert_no_task_dispatch,
    assert_oauth2_only,
    make_options,
)


def test_make_options_rejects_agent_in_allowed_tools():
    """G2: ``Agent`` in ``allowed_tools`` raises ``ValueError`` containing 'G2'."""
    with pytest.raises(ValueError) as exc:
        make_options(
            system_prompt="x",
            allowed_tools=["Agent", "Read"],
            permission_mode="dontAsk",
            max_turns=10,
            model="claude-haiku-4-5",
        )
    assert "G2" in str(exc.value)


def test_make_options_accepts_safe_tool_set():
    opt = make_options(
        system_prompt="x",
        allowed_tools=["Read", "Glob"],
        permission_mode="dontAsk",
        max_turns=10,
        model="claude-haiku-4-5",
    )
    assert opt.allowed_tools == ["Read", "Glob"]


def test_make_options_empty_allowed_tools_is_skill14_path():
    """RISK-04 happy path: empty ``allowed_tools`` and ``mcp_servers=None``."""
    opt = make_options(
        system_prompt="x",
        allowed_tools=[],
        permission_mode="dontAsk",
        max_turns=3,
        model="claude-haiku-4-5",
        mcp_servers=None,
    )
    assert opt.allowed_tools == []
    assert getattr(opt, "mcp_servers", None) in (None, {})


def test_make_options_passes_through_max_budget_usd():
    opt = make_options(
        system_prompt="x",
        allowed_tools=[],
        permission_mode="dontAsk",
        max_turns=3,
        model="claude-haiku-4-5",
        max_budget_usd=0.05,
    )
    budget = getattr(opt, "max_budget_usd", None)
    assert budget == 0.05 or "max_budget_usd" in opt.model_dump()


def test_g1_blocks_when_api_key_present(monkeypatch):
    """G1: ``assert_oauth2_only`` raises ``RuntimeError`` when ANTHROPIC_API_KEY is set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    with pytest.raises(RuntimeError) as exc:
        assert_oauth2_only()
    assert "G1" in str(exc.value)


def test_g1_make_options_blocks_when_api_key_present(monkeypatch):
    """G1: ``make_options`` raises ``RuntimeError`` if ``ANTHROPIC_API_KEY`` is
    set at call time."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    with pytest.raises(RuntimeError) as exc:
        make_options(
            system_prompt="x",
            allowed_tools=[],
            permission_mode="dontAsk",
            max_turns=3,
            model="claude-haiku-4-5",
        )
    assert "G1" in str(exc.value)


def test_g1_module_import_does_not_assert(monkeypatch):
    """G1 must be at function-entry, NOT module-import time. Setting
    ``ANTHROPIC_API_KEY`` then re-importing must succeed (proves the
    assertion is not at module top)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    import importlib

    from hsb.agents import _sdk_options as mod

    importlib.reload(mod)  # would fail if module-top assert fired
    assert hasattr(mod, "make_options")


def test_g3_raises_on_task_tool_in_assistant_message():
    """G3: real ``AssistantMessage`` with ``ToolUseBlock(name='Task')`` raises ``RuntimeError``.

    The production function uses a module-level import of ``AssistantMessage``
    from ``claude_agent_sdk``, so monkeypatching the module attribute after
    import has no effect. Instead, we use a real ``AssistantMessage`` instance
    (with a real ``ToolUseBlock``) so the ``isinstance`` check succeeds.
    """
    from claude_agent_sdk import AssistantMessage
    from claude_agent_sdk.types import ToolUseBlock

    block = ToolUseBlock(id="tu_1", name="Task", input={})
    msg = AssistantMessage(content=[block], model="claude-haiku-4-5")
    with pytest.raises(RuntimeError) as exc:
        assert_no_task_dispatch(msg)
    assert "G3" in str(exc.value)


def test_g3_does_not_raise_on_text_only_assistant_message():
    """G3 happy path: ``AssistantMessage`` with only ``TextBlock``s is allowed."""
    from claude_agent_sdk import AssistantMessage
    from claude_agent_sdk.types import TextBlock

    block = TextBlock(text="hello")
    msg = AssistantMessage(content=[block], model="claude-haiku-4-5")
    assert_no_task_dispatch(msg)  # no raise


def test_g3_raises_on_task_tool_in_result_message():
    """G3 backstop: ``ResultMessage`` with ``usage.tool_uses`` entry ``name=='Task'`` raises."""
    from claude_agent_sdk import ResultMessage

    msg = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
        usage={"tool_uses": [{"name": "Task", "count": 1}]},
    )
    with pytest.raises(RuntimeError) as exc:
        assert_no_task_dispatch(msg)
    assert "G3" in str(exc.value)


def test_g3_does_not_raise_on_safe_tool_in_result_message():
    """G3 happy path: ``ResultMessage`` with a non-Task tool entry does not raise."""
    from claude_agent_sdk import ResultMessage

    msg = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
        usage={"tool_uses": [{"name": "Read", "count": 2}]},
    )
    assert_no_task_dispatch(msg)  # no raise


def test_g3_does_not_raise_on_result_message_with_null_usage():
    """G3 resilience: ``ResultMessage`` with ``usage=None`` does not crash."""
    from claude_agent_sdk import ResultMessage

    msg = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
        usage=None,
    )
    assert_no_task_dispatch(msg)  # no raise, no AttributeError


def test_linear_write_guard_sync_denies_when_called_from_risk_agent(monkeypatch):
    """G5: sync Linear write originating from risk_agent.py raises ``PermissionError``.

    Patches the stack-inspection helper so the test does not need to actually
    call from inside risk_agent.py.
    """
    import hsb.agents._sdk_options as opts_mod
    from hsb.agents._sdk_options import linear_write_guard

    @linear_write_guard
    def my_write_fn():
        return "wrote"

    monkeypatch.setattr(
        opts_mod,
        "_stack_includes_risk_agent_excluding_delegated",
        lambda: True,
    )

    with pytest.raises(PermissionError) as exc:
        my_write_fn()
    assert "RISK-04" in str(exc.value)


def test_linear_write_guard_sync_allows_when_not_from_risk_agent(monkeypatch):
    """G5 happy path: sync Linear write NOT from risk_agent.py succeeds."""
    import hsb.agents._sdk_options as opts_mod
    from hsb.agents._sdk_options import linear_write_guard

    @linear_write_guard
    def my_write_fn():
        return "wrote"

    monkeypatch.setattr(
        opts_mod,
        "_stack_includes_risk_agent_excluding_delegated",
        lambda: False,
    )

    result = my_write_fn()
    assert result == "wrote"


def test_conftest_fixture_clears_anthropic_api_key():
    """Confirms the session-scoped autouse fixture in ``conftest.py``
    removed ``ANTHROPIC_API_KEY`` before this test ran."""
    assert "ANTHROPIC_API_KEY" not in os.environ, (
        "G1 defensive fixture failed: ANTHROPIC_API_KEY still in os.environ at test time"
    )
