"""Tool / MCP shape tests."""

import pytest

from llm_providers.tools import McpServerSpec, ToolPolicy, ToolSpec


def test_tool_spec_is_frozen():
    t = ToolSpec(
        name="read", description="read a file", input_schema={"type": "object"}
    )
    with pytest.raises(Exception):  # noqa: B017
        t.name = "x"  # type: ignore[misc]
    assert t.handler is None


def test_tool_policy_defaults_empty():
    p = ToolPolicy()
    assert p.allowed == ()
    assert p.denied == ()
    assert p.custom == ()


def test_tool_policy_can_carry_custom_tools():
    spec = ToolSpec(name="myfn", description="d", input_schema={})
    p = ToolPolicy(custom=(spec,))
    assert p.custom[0] is spec


def test_mcp_server_stdio():
    s = McpServerSpec(name="filesystem", transport="stdio", command=("npx", "fs-mcp"))
    assert s.transport == "stdio"
    assert s.url is None
    assert s.env == {}


def test_mcp_server_http():
    s = McpServerSpec(name="api", transport="http", url="http://localhost:8000")
    assert s.command is None
    assert s.url == "http://localhost:8000"
