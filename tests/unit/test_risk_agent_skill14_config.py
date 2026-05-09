"""RISK-04 + G3 + G4 structural tests for the skill 14 PydanticAI Agent."""
from __future__ import annotations

import pytest


def test_skill14_agent_has_no_tools_or_mcp():
    """RISK-04 structural: the module-level ``_risk_agent`` must have no tools
    and no toolsets registered (no MCP servers). Inspect the source — the
    Agent constructor must NOT pass tools= or toolsets=."""
    src = open("src/hsb/agents/risk_agent.py").read()
    # Find the _risk_agent = Agent(...) block
    import re
    match = re.search(r"_risk_agent[^=]*=\s*Agent\((.*?)\)\s*\n", src, re.DOTALL)
    assert match, "Could not find _risk_agent Agent(...) construction"
    agent_construct = match.group(1)
    # Must NOT have tools= or toolsets= keyword arguments
    assert "tools=" not in agent_construct, (
        f"RISK-04 violated: _risk_agent must have no tools=; got: {agent_construct}"
    )
    assert "toolsets=" not in agent_construct, (
        f"RISK-04 violated: _risk_agent must have no toolsets=; got: {agent_construct}"
    )
    assert 'AnthropicModel("claude-haiku' in agent_construct, (
        "Skill 14 must use claude-haiku model"
    )


def test_risk_agent_module_has_no_import_time_oauth_assert():
    """G1 is enforced via :func:`guards.assert_api_key_set`, NOT via a
    module-top assertion in ``risk_agent.py``."""
    src = open("src/hsb/agents/risk_agent.py").read()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert") and "ANTHROPIC_API_KEY" in stripped:
            raise AssertionError(
                "G1 must NOT be a module-top assert in risk_agent.py — it is "
                "enforced via guards.assert_api_key_set(). Found: " + line
            )


def test_risk_agent_does_not_import_linear_agent():
    """RISK-04 structural: ``RiskAgent`` never imports ``linear_agent``."""
    src = open("src/hsb/agents/risk_agent.py").read()
    assert "from hsb.agents.linear_agent" not in src, (
        "RISK-04 violated: risk_agent.py imports linear_agent"
    )


def test_risk_agent_imports_assert_no_task_dispatch():
    """G3 shim must be wired in ``risk_agent.py`` (preserved for source-grep)."""
    src = open("src/hsb/agents/risk_agent.py").read()
    assert "assert_no_task_dispatch" in src, (
        "G3: risk_agent.py does not import or call assert_no_task_dispatch — "
        "the source-grep contract requires it (noop shim in PydanticAI)."
    )


def test_risk_agent_calls_assert_no_task_dispatch():
    """G3 shim is called in the agent body (preserved for source-grep)."""
    src = open("src/hsb/agents/risk_agent.py").read()
    # In PydanticAI, there's no async for receive loop, but the shim must
    # still be called somewhere in detect_improvement_triggers
    assert "assert_no_task_dispatch(" in src, (
        "G3: assert_no_task_dispatch(...) must be called in risk_agent.py"
    )
