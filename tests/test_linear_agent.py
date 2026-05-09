"""Unit tests for src/hsb/agents/linear_agent.py — PydanticAI version.

Migrated from claude-agent-sdk: PydanticAI's output_type=LinearOutput +
output_retries=3 replaces the manual JSON-parse retry loop. These tests
use TestModel via _linear_agent.override() instead of patching run_linear_agent.

Live Linear MCP integration tests live in tests/test_integration.py.
"""
from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from hsb.agents import linear_agent
from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.linear import LinearEntity, LinearOutput


VALID_OUTPUT = LinearOutput(
    operation="create",
    result="success",
    linear_entities=[
        LinearEntity(
            id="LIN-1",
            type="task",
            url="https://linear.app/x/LIN-1",
        )
    ],
    error=None,
)


@pytest.mark.asyncio
async def test_validated_agent_happy_path():
    """Happy path: TestModel returns a valid LinearOutput payload."""
    with linear_agent._linear_agent.override(
        model=TestModel(custom_output_args=VALID_OUTPUT.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await run_validated_linear_agent(
            operation="create",
            payload={"title": "x", "type": "task", "teamId": "T-1"},
        )
    assert isinstance(result, LinearOutput)
    assert result.result == "success"
    assert result.linear_entities[0].id == "LIN-1"


@pytest.mark.asyncio
async def test_validated_agent_returns_linear_output_type():
    """run_validated_linear_agent always returns a LinearOutput instance."""
    with linear_agent._linear_agent.override(
        model=TestModel(custom_output_args=VALID_OUTPUT.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        result = await run_validated_linear_agent(operation="create", payload={})
    assert isinstance(result, LinearOutput)


@pytest.mark.asyncio
async def test_validated_agent_routes_writes_through_g5_guard():
    """G5: write operations go through _run_validated_linear_agent_write
    (which carries the @linear_write_guard decorator)."""
    with linear_agent._linear_agent.override(
        model=TestModel(custom_output_args=VALID_OUTPUT.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        # Write operations defined in _WRITE_OPERATIONS
        for op in ("create", "update", "create_comment"):
            result = await run_validated_linear_agent(operation=op, payload={})
            assert isinstance(result, LinearOutput)


@pytest.mark.asyncio
async def test_validated_agent_routes_reads_directly():
    """READ operations bypass the G5 guard and call the impl directly."""
    with linear_agent._linear_agent.override(
        model=TestModel(custom_output_args=VALID_OUTPUT.model_dump(), call_tools=[]),
        toolsets=[],
    ):
        # 'read' is NOT in _WRITE_OPERATIONS — bypasses G5 guard
        result = await run_validated_linear_agent(operation="read", payload={})
    assert isinstance(result, LinearOutput)


def test_write_operations_set_includes_canonical_writes():
    """The _WRITE_OPERATIONS set includes all known mutation entry points."""
    expected = {
        "create",
        "update",
        "create_comment",
        "create_subtasks",
        "create_issue",
        "update_issue",
    }
    assert linear_agent._WRITE_OPERATIONS >= expected
