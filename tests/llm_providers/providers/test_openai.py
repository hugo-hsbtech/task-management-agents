"""OpenAIProvider — dual-backend routing (Codex CLI vs raw OpenAI)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _isolate_openai_registration():
    """Each test re-imports llm_providers.providers.openai under a fresh
    stubbed SDK. patch.dict("sys.modules", ...) evicts the re-imported
    module on exit, so the decorator re-runs the next time — which would
    collide with the prior registration. Pop the entry around each test so
    re-registration is clean, and restore the original after so subsequent
    tests on the same xdist worker still see it registered."""
    import sys

    original = ProviderRegistry._providers.get("openai")
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)
    yield
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)
    if original is not None:
        ProviderRegistry._providers["openai"] = original


def _stub_codex_sdk():
    return SimpleNamespace(
        Codex=MagicMock(),
        TextInput=MagicMock(),
        ThreadOptions=MagicMock(),
        TurnOptions=MagicMock(),
        TurnCompletedEvent=type("TurnCompletedEvent", (), {}),
        TurnFailedEvent=type("TurnFailedEvent", (), {}),
        types=SimpleNamespace(CodexOptions=MagicMock()),
    )


def _stub_openai_sdk():
    return SimpleNamespace(OpenAI=MagicMock(), AsyncOpenAI=MagicMock())


def test_codex_backend_selected_for_oauth_token(monkeypatch, tmp_path):
    # Set up a valid Codex config so the backend init guard passes.
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _CodexBackend

        p = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert isinstance(p._backend, _CodexBackend)


def test_raw_openai_backend_selected_for_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _RawOpenAIBackend

        p = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert isinstance(p._backend, _RawOpenAIBackend)


def test_capabilities_differ_by_backend(monkeypatch, tmp_path):
    """supports_mcp is True only on the Codex backend."""
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    sdks_codex = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    sdks_raw = {"openai": _stub_openai_sdk()}

    with patch.dict("sys.modules", sdks_codex):
        from llm_providers.providers.openai import OpenAIProvider

        p_codex = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert p_codex.capabilities.supports_mcp is True

    # Reset registration so the second import re-runs the decorator cleanly.
    import sys

    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)

    with patch.dict("sys.modules", sdks_raw):
        from llm_providers.providers.openai import OpenAIProvider

        p_raw = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert p_raw.capabilities.supports_mcp is False


def test_supported_auth():
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        assert OAuth2CliToken in OpenAIProvider.supported_auth
        assert ApiKey in OpenAIProvider.supported_auth


def test_codex_backend_init_calls_oauth_guard(monkeypatch, tmp_path):
    """The Codex backend must verify ~/.codex/config.toml at init."""
    # auth.json exists so OAuth2CliToken.resolve() succeeds, but no config.toml
    # → the Codex backend's init-time guard should raise.
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        with pytest.raises(RuntimeError, match="config.toml not found"):
            OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))


@pytest.mark.asyncio
async def test_raw_openai_query_streams_messages(monkeypatch):
    """Smoke-test the raw OpenAI backend's async streaming path.

    Verifies the backend uses AsyncOpenAI (await chat.completions.create is
    valid) and yields a final Message after streaming.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")

    # Fake async iterator yielding two chunks then ending.
    chunk1 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="hello "))]
    )
    chunk2 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="world"))]
    )

    class _FakeStream:
        def __init__(self, chunks):
            self._chunks = iter(chunks)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._chunks)
            except StopIteration:
                raise StopAsyncIteration from None

    fake_create = AsyncMock(return_value=_FakeStream([chunk1, chunk2]))
    fake_completions = SimpleNamespace(create=fake_create)
    fake_chat = SimpleNamespace(completions=fake_completions)
    fake_async_client = SimpleNamespace(chat=fake_chat)

    fake_openai = SimpleNamespace(
        AsyncOpenAI=MagicMock(return_value=fake_async_client),
        OpenAI=MagicMock(),  # legacy attribute, should NOT be used
    )

    with patch.dict("sys.modules", {"openai": fake_openai}):
        from llm_providers.auth.api_key import ApiKey
        from llm_providers.prompt import TextSystemPrompt
        from llm_providers.protocol import ProviderOptions
        from llm_providers.providers.openai import OpenAIProvider
        from llm_providers.tools import ToolPolicy

        provider = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        opts = ProviderOptions(
            system_prompt=TextSystemPrompt(text="be helpful"),
            model="gpt-4o-mini",
            max_turns=5,
            tool_policy=ToolPolicy(),
        )

        msgs = []
        async for m in provider.query("hi", opts):
            msgs.append(m)

        # AsyncOpenAI was used, not sync OpenAI
        fake_openai.AsyncOpenAI.assert_called_once_with(api_key="sk-abc")
        fake_openai.OpenAI.assert_not_called()

        # At least one chunk message + one final message
        assert any(m.text == "hello " for m in msgs)
        assert any(m.text == "world" for m in msgs)
        assert msgs[-1].is_final is True
        assert msgs[-1].text == "hello world"
