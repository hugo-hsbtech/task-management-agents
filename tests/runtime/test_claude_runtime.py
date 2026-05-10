"""ClaudeRuntime: thin wrapper around claude_agent_sdk.query."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage

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
    fake_assistant = MagicMock(spec=AssistantMessage)
    fake_assistant.content = [fake_text_block]
    fake_result = MagicMock(spec=ResultMessage)
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
    from hsb.runtime.hooks import HookMatcher
    sentinel_hooks = {"PreToolUse": [HookMatcher(hooks=[lambda: None])]}
    opts_with_hooks = AgentOptions(**{**opts.__dict__, "hooks": sentinel_hooks})
    async def fake_iter(prompt, options):
        if False:
            yield  # never yields

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_iter) as q:
        rt = ClaudeRuntime()
        async for _ in rt.query("p", opts_with_hooks):
            pass
        sdk_options = q.call_args.kwargs["options"]
        assert "PreToolUse" in sdk_options.hooks
        translated_matcher = sdk_options.hooks["PreToolUse"][0]
        assert translated_matcher.matcher is None
        assert len(translated_matcher.hooks) == 1

# ---------------------------------------------------------------------------
# Coverage-gap tests: lines 31, 48, 60
# ---------------------------------------------------------------------------


def test_client_raises_not_implemented(opts):
    """Line 31: client() raises NotImplementedError matching 'not yet wired'."""
    rt = ClaudeRuntime()
    with pytest.raises(NotImplementedError, match=r"not yet wired"):
        rt.client(opts)


@pytest.mark.asyncio
async def test_translate_sets_cwd_when_provided(opts):
    """Line 48: _translate includes cwd in kwargs when options.cwd is not None."""
    from unittest.mock import AsyncMock, MagicMock, patch

    opts_with_cwd = AgentOptions(**{**opts.__dict__, "cwd": "/some/path"})

    async def fake_iter(prompt, options):
        if False:
            yield

    with patch(
        "hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_iter
    ) as q:
        rt = ClaudeRuntime()
        async for _ in rt.query("p", opts_with_cwd):
            pass

    sdk_options = q.call_args.kwargs["options"]
    assert sdk_options.cwd == "/some/path"


def test_to_message_unknown_type_returns_empty_non_final():
    """Line 60: _to_message with an unknown message type returns Message(text='', is_final=False)."""
    from claude_agent_sdk import SystemMessage

    from hsb.runtime.claude import ClaudeRuntime
    from hsb.runtime.protocol import Message

    # SystemMessage is neither AssistantMessage nor ResultMessage — hits the fallback.
    unknown = MagicMock(spec=SystemMessage)
    result = ClaudeRuntime._to_message(unknown)
    assert isinstance(result, Message)
    assert result.text == ""
    assert result.is_final is False
    assert result.raw is unknown
