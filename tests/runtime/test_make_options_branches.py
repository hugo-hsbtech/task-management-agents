"""Tests for the optional-kwarg branches in make_options().

Covers lines 104, 108, 110, 112 of src/hsb/agents/_sdk_options.py:
  - mcp_servers kwarg is forwarded when provided
  - max_budget_usd kwarg is forwarded when provided
  - cwd kwarg is forwarded when provided
  - resume kwarg is forwarded when provided

Note: lines 137-241 (G3 backstop + G5 linear_write_guard) are pre-existing
Phase 5 code and are NOT tested here.
"""
from __future__ import annotations

import pytest

from hsb.agents._sdk_options import make_options


@pytest.fixture(autouse=True)
def clear_api_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _base_kwargs():
    return dict(
        system_prompt="x",
        allowed_tools=[],
        permission_mode="acceptEdits",
        max_turns=1,
        model="claude-haiku-4-5",
    )


def test_make_options_passes_mcp_servers():
    """Line 104: mcp_servers is included in ClaudeAgentOptions when provided."""
    mcp = {"linear": {"command": "npx", "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]}}
    opt = make_options(**_base_kwargs(), mcp_servers=mcp)
    assert opt.mcp_servers == mcp


def test_make_options_passes_max_budget_usd():
    """Line 108: max_budget_usd is included in ClaudeAgentOptions when provided."""
    opt = make_options(**_base_kwargs(), max_budget_usd=1.5)
    assert opt.max_budget_usd == 1.5


def test_make_options_passes_cwd():
    """Line 110: cwd is included in ClaudeAgentOptions when provided."""
    opt = make_options(**_base_kwargs(), cwd="/tmp")
    assert opt.cwd == "/tmp"


def test_make_options_passes_resume():
    """Line 112: resume is included in ClaudeAgentOptions when provided."""
    opt = make_options(**_base_kwargs(), resume="session-abc-123")
    assert opt.resume == "session-abc-123"


def test_make_options_passes_tools():
    """Line 112: tools kwarg is included in ClaudeAgentOptions when provided."""
    opt = make_options(**_base_kwargs(), tools=["Bash"])
    assert getattr(opt, "tools", None) == ["Bash"]


def test_make_options_omits_optional_fields_when_not_provided():
    """When optional kwargs are omitted, they should be absent or have default values.
    mcp_servers defaults to {} (ClaudeAgentOptions default), max_budget_usd/cwd/resume are None."""
    opt = make_options(**_base_kwargs())
    # mcp_servers defaults to {} by ClaudeAgentOptions — not None
    assert getattr(opt, "mcp_servers", None) in (None, {})
    assert getattr(opt, "max_budget_usd", None) is None
    assert getattr(opt, "cwd", None) is None
    assert getattr(opt, "resume", None) is None
