"""Branch-coverage tests for ClaudeProvider — error classification, _build_sdk_env,
MCP/HTTP translation, options assembly, and StatefulClient error wrap."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import (
    ClaudeAuthError,
    ClaudeRateLimitError,
    ProviderRuntimeError,
    TranslationError,
)
from llm_providers.prompt import TextSystemPrompt
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


@pytest.fixture(autouse=True)
def _isolate_claude_registration():
    """Same pattern as the sibling provider test file — clean re-import."""
    import sys

    original_module = sys.modules.get("llm_providers.providers.claude")
    original_provider = ProviderRegistry._providers.get("claude")
    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)
    yield
    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)
    if original_module is not None:
        sys.modules["llm_providers.providers.claude"] = original_module
    if original_provider is not None:
        ProviderRegistry._providers["claude"] = original_provider


def _fake_sdk() -> SimpleNamespace:
    return SimpleNamespace(
        query=MagicMock(),
        ClaudeAgentOptions=MagicMock(),
        ClaudeSDKClient=MagicMock(),
        AssistantMessage=type("AssistantMessage", (), {}),
        ResultMessage=type("ResultMessage", (), {}),
    )


def _claude_provider(auth=None):
    with patch.dict("sys.modules", {"claude_agent_sdk": _fake_sdk()}):
        from llm_providers.providers.claude import ClaudeProvider

        return ClaudeProvider(auth=auth or OAuth2CliToken(token="tok-abc"))


# ---------------------------------------------------------------------------
# _build_sdk_env — all three branches
# ---------------------------------------------------------------------------


def test_build_sdk_env_oauth2_returns_token_var():
    provider = _claude_provider(auth=OAuth2CliToken(token="tok-1"))
    assert provider._sdk_env == {"CLAUDE_CODE_OAUTH_TOKEN": "tok-1"}


def test_build_sdk_env_api_key_returns_anthropic_var():
    provider = _claude_provider(auth=ApiKey(api_key="sk-1"))
    assert provider._sdk_env == {"ANTHROPIC_API_KEY": "sk-1"}


def test_build_sdk_env_unknown_kind_logs_and_returns_empty():
    """Static method on ClaudeProvider — exercisable without an instance."""
    with patch.dict("sys.modules", {"claude_agent_sdk": _fake_sdk()}):
        from llm_providers.providers.claude import ClaudeProvider

        cred = Credential(kind="oauth2_adc", payload={})  # type: ignore[arg-type]
        assert ClaudeProvider._build_sdk_env(cred) == {}


# ---------------------------------------------------------------------------
# _classify_exception — all four branches
# ---------------------------------------------------------------------------


def test_classify_exception_rate_limit_by_type_name():
    provider = _claude_provider()

    class RateLimitError(Exception):
        pass

    exc = RateLimitError("you hit your limit, resets 3pm UTC.")
    out = provider._classify_exception(exc)
    assert isinstance(out, ClaudeRateLimitError)
    assert out.reset_time == "3pm UTC"


def test_classify_exception_rate_limit_by_phrase_without_reset_time():
    provider = _claude_provider()

    out = provider._classify_exception(Exception("hit your limit"))
    assert isinstance(out, ClaudeRateLimitError)
    assert out.reset_time is None


def test_classify_exception_auth_by_type_name():
    provider = _claude_provider()

    class AuthenticationError(Exception):
        pass

    out = provider._classify_exception(AuthenticationError("bad creds"))
    assert isinstance(out, ClaudeAuthError)


def test_classify_exception_auth_by_phrase():
    provider = _claude_provider()
    out = provider._classify_exception(Exception("oauth_token_invalid"))
    assert isinstance(out, ClaudeAuthError)


def test_classify_exception_malformed_error_result():
    provider = _claude_provider()
    out = provider._classify_exception(Exception("error result: success"))
    assert isinstance(out, ProviderRuntimeError)
    assert "malformed" in str(out)


def test_classify_exception_generic_fallback():
    provider = _claude_provider()
    out = provider._classify_exception(Exception("something else"))
    assert isinstance(out, ProviderRuntimeError)
    assert "Claude query failed" in str(out)


# ---------------------------------------------------------------------------
# _translate_system_prompt unknown subtype
# ---------------------------------------------------------------------------


def test_translate_system_prompt_unknown_subtype_raises():
    provider = _claude_provider()

    class _Bogus:
        pass

    with pytest.raises(TranslationError, match="Unknown SystemPrompt"):
        provider._translate_system_prompt(_Bogus())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _translate_mcp — http + env + unknown-transport branches
# ---------------------------------------------------------------------------


def test_translate_mcp_http_with_url_and_env():
    provider = _claude_provider()
    spec = McpServerSpec(
        name="remote",
        transport="http",
        url="https://example.com/mcp",
        env={"FOO": "bar"},
    )
    out = provider._translate_mcp((spec,))
    assert "remote" in out
    assert out["remote"]["transport"] == "stdio"
    assert "mcp-remote" in out["remote"]["command"]
    assert out["remote"]["env"] == {"FOO": "bar"}


def test_translate_mcp_stdio_with_env():
    provider = _claude_provider()
    spec = McpServerSpec(
        name="local",
        transport="stdio",
        command=("npx", "x"),
        env={"K": "V"},
    )
    out = provider._translate_mcp((spec,))
    assert out["local"]["env"] == {"K": "V"}


def test_translate_mcp_rejects_unknown_transport():
    provider = _claude_provider()
    spec = McpServerSpec(
        name="bad",
        transport="grpc",
        url="x",  # type: ignore[arg-type]
    )
    with pytest.raises(TranslationError, match="unsupported transport"):
        provider._translate_mcp((spec,))


# ---------------------------------------------------------------------------
# _build_native_options — mcp / cwd / hooks branches
# ---------------------------------------------------------------------------


def test_build_native_options_propagates_mcp_cwd_hooks():
    provider = _claude_provider()
    spec = McpServerSpec(name="local", transport="stdio", command=("npx", "x"))
    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="prompt"),
        model="claude-haiku-4-5",
        max_turns=3,
        tool_policy=ToolPolicy(),
        mcp_servers=(spec,),
        cwd="/work",
        extras={"claude": {"hooks": ["hook-a"]}},
    )
    provider._build_native_options(opts)
    kwargs = provider._sdk.ClaudeAgentOptions.call_args.kwargs
    assert "mcp_servers" in kwargs
    assert kwargs["cwd"] == "/work"
    assert kwargs["hooks"] == ["hook-a"]


# ---------------------------------------------------------------------------
# _to_message — non-success subtype, AssistantMessage, fallback
# ---------------------------------------------------------------------------


def test_to_message_result_non_success_raises():
    provider = _claude_provider()
    sdk = provider._sdk

    class _Result(sdk.ResultMessage):
        pass

    msg = _Result()
    msg.subtype = "failure"
    with pytest.raises(RuntimeError, match="Claude agent failed"):
        provider._to_message(msg)


def test_to_message_result_falls_back_to_result_attr():
    provider = _claude_provider()
    sdk = provider._sdk

    class _Result(sdk.ResultMessage):
        pass

    msg = _Result()
    msg.subtype = "success"
    msg.structured_output = None
    msg.result = "plain text"
    out = provider._to_message(msg)
    assert out.text == "plain text"
    assert out.is_final


def test_to_message_assistant_message_concats_content():
    provider = _claude_provider()
    sdk = provider._sdk

    class _Assistant(sdk.AssistantMessage):
        pass

    msg = _Assistant()
    msg.content = [SimpleNamespace(text="hello "), SimpleNamespace(text="world")]
    out = provider._to_message(msg)
    assert out.text == "hello world"
    assert not out.is_final


def test_to_message_unknown_type_returns_empty_message():
    provider = _claude_provider()
    out = provider._to_message(object())
    assert out.text == ""
    assert not out.is_final


# ---------------------------------------------------------------------------
# query() / client() error wrapping
# ---------------------------------------------------------------------------


def test_query_wraps_sdk_exception_via_classify():
    provider = _claude_provider()

    async def _raising_query(**_kw: Any):
        yield None  # pragma: no cover (never reached — generator raises before first yield)
        raise Exception("oauth_token_invalid")

    # Patch sdk.query to return an async generator that raises.
    async def _raise(*_a: Any, **_k: Any):
        raise Exception("oauth_token_invalid")
        yield  # pragma: no cover - makes function an async generator

    provider._sdk.query = _raise

    async def _run():
        async for _ in provider.query("hi", _opts()):
            pass  # pragma: no cover - never reached

    with pytest.raises(ClaudeAuthError):
        asyncio.run(_run())


def test_client_wraps_init_failure():
    provider = _claude_provider()
    provider._sdk.ClaudeSDKClient.side_effect = RuntimeError("init boom")
    with pytest.raises(ProviderRuntimeError, match="client_init"):
        provider.client(_opts())


def test_stateful_client_wraps_query_failure():
    provider = _claude_provider()

    fake_sdk_client = MagicMock()

    async def _aenter():
        return fake_sdk_client

    fake_sdk_client.__aenter__ = lambda self: _aenter()
    fake_sdk_client.__aexit__ = MagicMock(return_value=None)

    async def _raise_during_query(_prompt):
        raise RuntimeError("query blew up")
        yield  # pragma: no cover - makes generator

    fake_sdk_client.query = _raise_during_query
    provider._sdk.ClaudeSDKClient.return_value = fake_sdk_client

    async def _run():
        client = provider.client(_opts())
        async for _ in client.query("hi"):
            pass  # pragma: no cover

    with pytest.raises(ProviderRuntimeError, match="client_query"):
        asyncio.run(_run())


def _opts() -> ProviderOptions:
    return ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="claude-haiku-4-5",
        max_turns=3,
        tool_policy=ToolPolicy(),
    )


def test_message_dataclass_is_constructible():
    """Sanity check: Message contract holds for asserts above."""
    m = Message(text="x", is_final=True)
    assert m.text == "x"


def test_stateful_client_aenter_aexit_delegate():
    """_ClaudeStatefulClient.__aenter__/__aexit__ must delegate to the wrapped
    SDK client so the async-context-manager protocol works end-to-end."""
    provider = _claude_provider()

    fake_inner = MagicMock()
    aenter_called = MagicMock()
    aexit_called = MagicMock()

    async def _aenter():
        aenter_called()

    async def _aexit(*exc):
        aexit_called(*exc)

    fake_inner.__aenter__ = lambda self: _aenter()
    fake_inner.__aexit__ = lambda self, *exc: _aexit(*exc)

    async def _empty_iter(_prompt):
        return
        yield  # pragma: no cover

    fake_inner.query = _empty_iter
    provider._sdk.ClaudeSDKClient.return_value = fake_inner

    async def _run():
        async with provider.client(_opts()) as client:
            async for _ in client.query("hi"):
                pass  # pragma: no cover

    asyncio.run(_run())
    aenter_called.assert_called_once()
    aexit_called.assert_called_once()


def test_stateful_client_passes_provider_runtime_error_through():
    """If the wrapped client raises a ProviderRuntimeError directly, the
    stateful adapter must NOT re-wrap it — preserves the original cause."""
    provider = _claude_provider()
    sentinel = ProviderRuntimeError(
        provider="claude", phase="query", message="orig msg"
    )

    fake_inner = MagicMock()

    async def _aenter():
        pass

    fake_inner.__aenter__ = lambda self: _aenter()
    fake_inner.__aexit__ = lambda self, *exc: _aenter()

    async def _raise(_prompt):
        raise sentinel
        yield  # pragma: no cover

    fake_inner.query = _raise
    provider._sdk.ClaudeSDKClient.return_value = fake_inner

    async def _run():
        async with provider.client(_opts()) as client:
            async for _ in client.query("hi"):
                pass  # pragma: no cover

    with pytest.raises(ProviderRuntimeError) as exc:
        asyncio.run(_run())
    assert exc.value is sentinel
