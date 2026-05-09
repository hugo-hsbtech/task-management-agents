"""ClaudeRuntime: thin wrapper around claude_agent_sdk.query."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.runtime.claude import ClaudeRuntime
from hsb.runtime.protocol import AgentOptions


@pytest.fixture
def opts():
    return AgentOptions(
        system_prompt="sys",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
        mcp_servers={"linear": {"command": "npx", "args": []}},
    )


def test_name_is_claude():
    assert ClaudeRuntime().name == "claude"


@pytest.mark.asyncio
async def test_query_translates_options_and_yields_messages(opts):
    fake_text_block = MagicMock(text="result chunk")
    fake_assistant = MagicMock()
    fake_assistant.content = [fake_text_block]
    fake_result = MagicMock()
    fake_result.usage = {"output_tokens": 10}

    async def fake_query_iter(prompt, options):
        yield fake_assistant
        yield fake_result

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query_iter) as q:
        rt = ClaudeRuntime()
        msgs = []
        async for m in rt.query("hello", opts):
            msgs.append(m)

    assert q.call_count == 1
    sdk_options = q.call_args.kwargs["options"]
    # Translation: AgentOptions → ClaudeAgentOptions preserves these fields.
    assert sdk_options.system_prompt == "sys"
    assert "Read" in sdk_options.allowed_tools
    assert sdk_options.permission_mode == "acceptEdits"
    assert sdk_options.max_turns == 5
    assert sdk_options.model == "claude-opus-4-7"
    assert sdk_options.mcp_servers == {"linear": {"command": "npx", "args": []}}
    # At least one message yielded with text content.
    assert any(m.text == "result chunk" for m in msgs)


@pytest.mark.asyncio
async def test_query_forwards_hooks_unchanged(opts):
    sentinel_hooks = ["hook1", "hook2"]
    opts_with_hooks = AgentOptions(**{**opts.__dict__, "hooks": sentinel_hooks})

    async def fake_iter(prompt, options):
        if False:
            yield  # never yields

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_iter) as q:
        rt = ClaudeRuntime()
        async for _ in rt.query("p", opts_with_hooks):
            pass
        sdk_options = q.call_args.kwargs["options"]
        assert sdk_options.hooks == sentinel_hooks
