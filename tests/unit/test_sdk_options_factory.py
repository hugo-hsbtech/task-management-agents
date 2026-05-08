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


class _StubBlock:
    def __init__(self, name=None, text=None):
        self.name = name
        self.text = text


class _StubAssistantMessage:
    def __init__(self, content):
        self.content = content


def test_g3_raises_on_task_tool_in_assistant_message(monkeypatch):
    """G3: ``AssistantMessage`` with content block ``name=='Task'`` raises ``RuntimeError``."""
    monkeypatch.setattr(
        "claude_agent_sdk.AssistantMessage",
        _StubAssistantMessage,
        raising=False,
    )
    msg = _StubAssistantMessage(content=[_StubBlock(name="Task")])
    with pytest.raises(RuntimeError) as exc:
        assert_no_task_dispatch(msg)
    assert "G3" in str(exc.value)


def test_g3_does_not_raise_on_text_only_assistant_message(monkeypatch):
    """G3 happy path: ``AssistantMessage`` with only ``TextBlock``s is allowed."""
    monkeypatch.setattr(
        "claude_agent_sdk.AssistantMessage",
        _StubAssistantMessage,
        raising=False,
    )
    msg = _StubAssistantMessage(content=[_StubBlock(name=None, text="hello")])
    assert_no_task_dispatch(msg)  # no raise


def test_conftest_fixture_clears_anthropic_api_key():
    """Confirms the session-scoped autouse fixture in ``conftest.py``
    removed ``ANTHROPIC_API_KEY`` before this test ran."""
    assert "ANTHROPIC_API_KEY" not in os.environ, (
        "G1 defensive fixture failed: ANTHROPIC_API_KEY still in os.environ at test time"
    )
