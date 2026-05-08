"""Unit tests for src/hsb/agents/linear_agent.py validation-retry layer.

Live Linear MCP integration tests live in tests/test_integration.py (Plan 05).
These tests patch run_linear_agent to control its returned result text.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from hsb.agents import linear_agent
from hsb.agents.linear_agent import (
    MAX_VALIDATION_RETRIES,
    run_validated_linear_agent,
)
from hsb.contracts.linear import LinearOutput

VALID_OUTPUT_JSON = json.dumps(
    {
        "operation": "create",
        "result": "success",
        "linear_entities": [
            {
                "id": "LIN-1",
                "type": "task",
                "url": "https://linear.app/x/LIN-1",
            }
        ],
        "error": None,
    }
)


@pytest.mark.asyncio
async def test_validated_agent_happy_path():
    with patch.object(
        linear_agent, "run_linear_agent", new=AsyncMock(return_value=VALID_OUTPUT_JSON)
    ):
        result = await run_validated_linear_agent(
            operation="create",
            payload={"title": "x", "type": "task", "teamId": "T-1"},
        )
    assert isinstance(result, LinearOutput)
    assert result.result == "success"
    assert result.linear_entities[0].id == "LIN-1"


@pytest.mark.asyncio
async def test_validated_agent_extracts_json_from_markdown():
    wrapped = f"Here is the result:\n```json\n{VALID_OUTPUT_JSON}\n```\nDone."
    with patch.object(
        linear_agent, "run_linear_agent", new=AsyncMock(return_value=wrapped)
    ):
        result = await run_validated_linear_agent(operation="create", payload={})
    assert result.linear_entities[0].id == "LIN-1"


@pytest.mark.asyncio
async def test_validated_agent_recovers_from_invalid_json_then_succeeds():
    call_count = {"n": 0}

    async def fake_runner(prompt: str):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return "this is not JSON at all"
        return VALID_OUTPUT_JSON

    with patch.object(linear_agent, "run_linear_agent", new=fake_runner):
        result = await run_validated_linear_agent(operation="create", payload={})
    assert result.result == "success"
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_validated_agent_raises_after_max_retries_invalid_json():
    with (
        patch.object(
            linear_agent,
            "run_linear_agent",
            new=AsyncMock(return_value="not JSON not JSON"),
        ),
        pytest.raises(ValueError) as exc_info,
    ):
        await run_validated_linear_agent(operation="create", payload={})
    assert f"after {MAX_VALIDATION_RETRIES} attempts" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validated_agent_raises_on_pydantic_validation_failure():
    # extra field rejected by extra=forbid
    bad_payload = json.dumps(
        {
            "operation": "create",
            "result": "success",
            "linear_entities": [],
            "error": None,
            "extra_field": "fail_me",
        }
    )
    with (
        patch.object(
            linear_agent, "run_linear_agent", new=AsyncMock(return_value=bad_payload)
        ),
        pytest.raises(ValueError) as exc_info,
    ):
        await run_validated_linear_agent(operation="create", payload={})
    assert "after 3 attempts" in str(exc_info.value)
    # The last_error should be a pydantic ValidationError
    assert "extra_field" in str(exc_info.value).lower() or "Last error" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_validated_agent_handles_none_result():
    call_count = {"n": 0}

    async def fake_runner(prompt: str):
        call_count["n"] += 1
        if call_count["n"] < 2:
            return None
        return VALID_OUTPUT_JSON

    with patch.object(linear_agent, "run_linear_agent", new=fake_runner):
        result = await run_validated_linear_agent(operation="create", payload={})
    assert result.result == "success"
