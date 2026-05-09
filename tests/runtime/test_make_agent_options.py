"""make_agent_options factory — runtime-agnostic AgentOptions builder."""
from __future__ import annotations

import pytest

from hsb.agents._sdk_options import make_agent_options
from hsb.runtime.protocol import AgentOptions


def test_returns_agent_options_dataclass(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    opts = make_agent_options(
        system_prompt="sys",
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
    )
    assert isinstance(opts, AgentOptions)
    assert opts.allowed_tools == ("Read",)


def test_runs_g1_oauth_guard(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    with pytest.raises(RuntimeError, match=r"G1 violation"):
        make_agent_options(
            system_prompt="x",
            allowed_tools=[],
            permission_mode="default",
            max_turns=1,
            model="m",
        )


def test_runs_g2_forbidden_tool_guard(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match=r"G2 violation"):
        make_agent_options(
            system_prompt="x",
            allowed_tools=["Agent"],
            permission_mode="default",
            max_turns=1,
            model="m",
        )


def test_optional_fields_passthrough(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    opts = make_agent_options(
        system_prompt="x",
        allowed_tools=[],
        permission_mode="default",
        max_turns=1,
        model="m",
        mcp_servers={"linear": {"command": "npx"}},
        cwd="/tmp",
        hooks=["sentinel"],
    )
    assert opts.mcp_servers == {"linear": {"command": "npx"}}
    assert opts.cwd == "/tmp"
    assert opts.hooks == ["sentinel"]
