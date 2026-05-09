"""Tests for src/hsb/agents/guards.py — replaces old test_sdk_options_factory.py.

PydanticAI inverts G1: ANTHROPIC_API_KEY must be PRESENT (not absent).
G2: validate_tool_list still rejects "Agent".
G3: noop shim, kept for source-grep compatibility.
G5: linear_write_guard preserved (tested separately in test_linear_write_guard_g5.py).
"""
from __future__ import annotations

import os

import pytest

from hsb.agents.guards import (
    assert_api_key_set,
    assert_no_task_dispatch,
    validate_tool_list,
)


def test_g1_raises_when_api_key_absent(monkeypatch):
    """G1 (PydanticAI): assert_api_key_set raises if ANTHROPIC_API_KEY missing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        assert_api_key_set()


def test_g1_passes_when_api_key_present(monkeypatch):
    """G1 (PydanticAI): assert_api_key_set returns None when key set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    result = assert_api_key_set()
    assert result is None


def test_g2_rejects_agent_in_tool_list():
    """G2 (WORC-02): validate_tool_list raises ValueError if 'Agent' present."""
    with pytest.raises(ValueError, match="G2 violation"):
        validate_tool_list(["Read", "Agent", "Write"])


def test_g2_accepts_safe_tool_list():
    """G2: validate_tool_list passes for safe lists."""
    validate_tool_list(["Read", "Edit", "Write", "Bash"])  # no raise
    validate_tool_list([])  # empty also fine


def test_g3_noop_on_any_object():
    """G3: assert_no_task_dispatch is a noop shim — accepts anything, returns None."""
    assert assert_no_task_dispatch(None) is None
    assert assert_no_task_dispatch(object()) is None
    assert assert_no_task_dispatch({"foo": "bar"}) is None
    assert assert_no_task_dispatch("anything") is None
