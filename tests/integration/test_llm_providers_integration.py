"""Cross-module integration tests for the llm_providers library and the
hsb.runtime consumer adapter.

These tests exercise the wiring as a complete system — registry →
provider construction → query → message conversion → handle → G3
backstop — without each individual module's mock isolation. SDK modules
are stubbed via ``patch.dict("sys.modules", ...)`` so the tests do not
require a real Claude or OpenAI install.

Convention: placed under ``tests/integration/`` next to the existing
parity tests, but deliberately NOT marked with ``@pytest.mark.integration``
(which the project reserves for live-API tests per ``pyproject.toml``).
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_providers.errors import AuthResolutionError
from llm_providers.prompt import SkillReference, TextSystemPrompt
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import ToolPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from llm_providers.base import BaseProvider, StatefulClient

# ---------------------------------------------------------------------------
# SDK stubs
# ---------------------------------------------------------------------------


def _stub_claude_sdk() -> SimpleNamespace:
    return SimpleNamespace(
        query=MagicMock(),
        ClaudeAgentOptions=MagicMock(),
        ClaudeSDKClient=MagicMock(),
        AssistantMessage=type("AssistantMessage", (), {}),
        ResultMessage=type("ResultMessage", (), {}),
    )


def _stub_openai_sdk(async_client: Any = None) -> SimpleNamespace:
    return SimpleNamespace(
        OpenAI=MagicMock(),
        AsyncOpenAI=MagicMock(return_value=async_client)
        if async_client is not None
        else MagicMock(),
    )


def _fake_async_openai_client(chunks: list[Any]) -> Any:
    """An AsyncOpenAI stand-in that returns an async-iterable stream from
    chat.completions.create."""

    class _FakeStream:
        def __init__(self, items: list[Any]) -> None:
            self._items = iter(items)

        def __aiter__(self) -> _FakeStream:
            return self

        async def __anext__(self) -> Any:
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration from None

    fake_create = AsyncMock(return_value=_FakeStream(chunks))
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )


# ---------------------------------------------------------------------------
# Fixtures: clean registration + isolated registries per test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_provider_registration() -> Any:
    """Each test re-imports the provider modules under a fresh stubbed SDK,
    so we evict cached modules and registry entries around every test (same
    pattern as the per-provider unit tests)."""
    for mod in (
        "llm_providers.providers.claude",
        "llm_providers.providers.openai",
    ):
        sys.modules.pop(mod, None)
    ProviderRegistry._providers.pop("claude", None)
    ProviderRegistry._providers.pop("openai", None)
    yield
    for mod in (
        "llm_providers.providers.claude",
        "llm_providers.providers.openai",
    ):
        sys.modules.pop(mod, None)
    ProviderRegistry._providers.pop("claude", None)
    ProviderRegistry._providers.pop("openai", None)


# ---------------------------------------------------------------------------
# Test 1 — end-to-end provider build via registry (Claude)
# ---------------------------------------------------------------------------


def test_registry_builds_claude_provider_and_query_yields_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ProviderRegistry.build_auto("claude") wires the OAuth env-var
    strategy and the resulting provider streams Message objects from a
    stubbed claude_agent_sdk.query."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-abc")

    fake_sdk = _stub_claude_sdk()
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        # Import inside the patch so the module-level `import claude_agent_sdk`
        # picks up the stub.
        from llm_providers.providers.claude import (
            ClaudeProvider,
            _ClaudeOAuth2CliToken,
        )

        provider = ProviderRegistry.build_auto("claude")

        assert isinstance(provider, ClaudeProvider)
        # The OAuth2 env-var strategy is preferred and detected via the
        # CLAUDE_CODE_OAUTH_TOKEN env var — the resolved strategy should be
        # the provider-private subclass added in Task 18, NOT the bare
        # OAuth2CliToken.
        assert isinstance(provider._auth, _ClaudeOAuth2CliToken)

        # Wire the stubbed SDK to yield one assistant + one result.
        msg_assistant = MagicMock(spec=fake_sdk.AssistantMessage)
        msg_assistant.content = [SimpleNamespace(text="hello world")]
        msg_result = MagicMock(spec=fake_sdk.ResultMessage)

        async def _aiter(prompt: str, options: Any) -> AsyncIterator[Any]:
            yield msg_assistant
            yield msg_result

        fake_sdk.query.side_effect = _aiter

        opts = ProviderOptions(
            system_prompt=TextSystemPrompt(text="be helpful"),
            model="claude-sonnet-4-6",
            max_turns=5,
            tool_policy=ToolPolicy(),
        )

        async def _run() -> list[Message]:
            collected: list[Message] = []
            async for m in provider.query("hi", opts):
                collected.append(m)
            return collected

        msgs = asyncio.run(_run())

    assert len(msgs) == 2
    assert msgs[0].text == "hello world"
    assert msgs[0].is_final is False
    assert msgs[-1].is_final is True


# ---------------------------------------------------------------------------
# Test 2 — end-to-end provider build via registry (OpenAI / API key)
# ---------------------------------------------------------------------------


def test_registry_builds_openai_provider_with_api_key_and_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ProviderRegistry.build_auto("openai", accepted_kinds={"api_key"})
    selects the _RawOpenAIBackend and streams chunks via AsyncOpenAI."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    chunk1 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="hel"))]
    )
    chunk2 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))]
    )
    async_client = _fake_async_openai_client([chunk1, chunk2])
    fake_openai = _stub_openai_sdk(async_client=async_client)

    with patch.dict("sys.modules", {"openai": fake_openai}):
        from llm_providers.providers.openai import (
            OpenAIProvider,
            _RawOpenAIBackend,
        )

        provider = ProviderRegistry.build_auto("openai", accepted_kinds={"api_key"})

        assert isinstance(provider, OpenAIProvider)
        assert isinstance(provider._backend, _RawOpenAIBackend)
        # The raw OpenAI backend does NOT support MCP.
        assert provider.capabilities.supports_mcp is False

        opts = ProviderOptions(
            system_prompt=TextSystemPrompt(text="be helpful"),
            model="gpt-4o-mini",
            max_turns=5,
            tool_policy=ToolPolicy(),
        )

        async def _run() -> list[Message]:
            collected: list[Message] = []
            async for m in provider.query("hi", opts):
                collected.append(m)
            return collected

        msgs = asyncio.run(_run())

    fake_openai.AsyncOpenAI.assert_called_once_with(api_key="sk-xyz")
    # Two streamed chunks + one synthesized final aggregate.
    assert [m.text for m in msgs[:2]] == ["hel", "lo"]
    assert msgs[-1].is_final is True
    assert msgs[-1].text == "hello"


# ---------------------------------------------------------------------------
# Test 3 — HsbProviderHandle integration via resolve_runtime
# ---------------------------------------------------------------------------


def test_resolve_runtime_returns_handle_wrapping_claude_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HSB_RUNTIME_BACKLOG=claude with CLAUDE_CODE_OAUTH_TOKEN set should
    resolve to an HsbProviderHandle around the ClaudeProvider, and the
    handle's query() should yield G3-wrapped messages.

    Uses the real ``claude_agent_sdk`` (already installed as a project
    dep) and patches only ``claude_agent_sdk.query`` so the hsb-side
    ``_sdk_options`` import inside ``HsbProviderHandle.query`` resolves
    against the real SDK types.
    """
    import claude_agent_sdk

    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")

    from hsb.runtime.handle import HsbProviderHandle
    from hsb.runtime.resolver import resolve_runtime
    from llm_providers.providers.claude import ClaudeProvider

    handle = resolve_runtime("backlog")

    assert isinstance(handle, HsbProviderHandle)
    assert isinstance(handle.provider, ClaudeProvider)
    assert handle.name == "claude"

    # Build a real AssistantMessage (no Task tool_use block) and a real
    # ResultMessage so G3 inspection sees the right isinstance type.
    text_block = SimpleNamespace(text="ok")
    fake_assistant = claude_agent_sdk.AssistantMessage.__new__(
        claude_agent_sdk.AssistantMessage
    )
    fake_assistant.content = [text_block]  # type: ignore[list-item]
    fake_result = MagicMock(spec=claude_agent_sdk.ResultMessage)

    async def _aiter(prompt: str, options: Any) -> AsyncIterator[Any]:
        yield fake_assistant
        yield fake_result

    monkeypatch.setattr(claude_agent_sdk, "query", _aiter)

    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="claude-sonnet-4-6",
        max_turns=5,
        tool_policy=ToolPolicy(),
    )

    async def _run() -> list[Message]:
        collected: list[Message] = []
        async for m in handle.query("hi", opts):
            collected.append(m)
        return collected

    msgs = asyncio.run(_run())

    assert len(msgs) == 2
    assert msgs[-1].is_final is True


# ---------------------------------------------------------------------------
# Test 4 — G3 backstop fires through the handle
# ---------------------------------------------------------------------------


def test_handle_g3_backstop_fires_on_task_tool_use() -> None:
    """A fake provider yielding an AssistantMessage with a 'Task' tool_use
    block must trip the G3 backstop inside HsbProviderHandle.query()."""
    from claude_agent_sdk import AssistantMessage

    from hsb.runtime.handle import HsbProviderHandle

    task_block = SimpleNamespace(name="Task")
    fake_assistant = AssistantMessage.__new__(AssistantMessage)
    fake_assistant.content = [task_block]  # type: ignore[list-item]

    class _BadProvider:
        name = "fake"

        async def query(
            self, prompt: str, options: ProviderOptions
        ) -> AsyncIterator[Message]:
            yield Message(text="", is_final=False, raw=fake_assistant)

        def client(self, options: ProviderOptions) -> StatefulClient:
            return cast("StatefulClient", MagicMock())

    handle = HsbProviderHandle(
        provider=cast("BaseProvider", _BadProvider()),
        agent_name="backlog",
    )

    opts = cast("ProviderOptions", SimpleNamespace())

    async def _run() -> None:
        async for _ in handle.query("hi", options=opts):
            pass

    with pytest.raises(RuntimeError, match="G3 violation"):
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5 — Conformance: same ProviderOptions works on both providers
# ---------------------------------------------------------------------------


def test_same_provider_options_works_against_both_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Liskov contract: a single ProviderOptions instance feeds both
    ClaudeProvider and OpenAIProvider (raw backend) and both terminate
    their async iterator with is_final=True."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-abc")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="m",
        max_turns=5,
        tool_policy=ToolPolicy(),
    )

    # ---- Claude side ----
    fake_claude_sdk = _stub_claude_sdk()
    msg_assistant = MagicMock(spec=fake_claude_sdk.AssistantMessage)
    msg_assistant.content = [SimpleNamespace(text="claude-out")]
    msg_result = MagicMock(spec=fake_claude_sdk.ResultMessage)

    async def _claude_aiter(prompt: str, options: Any) -> AsyncIterator[Any]:
        yield msg_assistant
        yield msg_result

    fake_claude_sdk.query.side_effect = _claude_aiter

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_claude_sdk}):
        from llm_providers.providers.claude import ClaudeProvider

        claude_provider = ProviderRegistry.build_auto("claude")
        assert isinstance(claude_provider, ClaudeProvider)

        async def _run_claude() -> list[Message]:
            collected: list[Message] = []
            async for m in claude_provider.query("hi", opts):
                collected.append(m)
            return collected

        claude_msgs = asyncio.run(_run_claude())

    # Evict the claude registration before constructing openai so the
    # autouse-fixture cleanup logic stays consistent (already handled by
    # the per-test fixture, but the second build_auto call inside the same
    # test needs the OpenAI module fresh too).
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)

    # ---- OpenAI side ----
    chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="openai-out"))]
    )
    async_client = _fake_async_openai_client([chunk])
    fake_openai = _stub_openai_sdk(async_client=async_client)

    with patch.dict("sys.modules", {"openai": fake_openai}):
        from llm_providers.providers.openai import OpenAIProvider

        openai_provider = ProviderRegistry.build_auto(
            "openai", accepted_kinds={"api_key"}
        )
        assert isinstance(openai_provider, OpenAIProvider)

        async def _run_openai() -> list[Message]:
            collected: list[Message] = []
            async for m in openai_provider.query("hi", opts):
                collected.append(m)
            return collected

        openai_msgs = asyncio.run(_run_openai())

    # Both providers must yield at least one final Message.
    assert any(m.is_final for m in claude_msgs)
    assert any(m.is_final for m in openai_msgs)


# ---------------------------------------------------------------------------
# Test 6 — SkillReference resolution across providers
# ---------------------------------------------------------------------------


def test_skill_reference_resolves_to_file_contents_for_both_providers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """A SkillReference pointing at a real file must be translated to that
    file's contents by both ClaudeProvider and the OpenAIProvider raw
    backend (and by extension the Codex backend, which uses the same
    shared _translate_system_prompt)."""
    skill = tmp_path / "skill.md"
    skill.write_text("skill body", encoding="utf-8")

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    # Claude side.
    fake_claude_sdk = _stub_claude_sdk()
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_claude_sdk}):
        from llm_providers.providers.claude import ClaudeProvider

        claude_provider = ProviderRegistry.build_auto("claude")
        assert isinstance(claude_provider, ClaudeProvider)
        claude_text = claude_provider._translate_system_prompt(
            SkillReference(path=skill)
        )
        assert claude_text == "skill body"

    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)

    # OpenAI side (raw backend).
    fake_openai = _stub_openai_sdk(async_client=_fake_async_openai_client([]))
    with patch.dict("sys.modules", {"openai": fake_openai}):
        from llm_providers.providers.openai import OpenAIProvider

        openai_provider = ProviderRegistry.build_auto(
            "openai", accepted_kinds={"api_key"}
        )
        assert isinstance(openai_provider, OpenAIProvider)
        openai_text = openai_provider._translate_system_prompt(
            SkillReference(path=skill)
        )
        assert openai_text == "skill body"


# ---------------------------------------------------------------------------
# Test 7 — Per-agent API-key escape hatch
# ---------------------------------------------------------------------------


def test_per_agent_api_key_escape_hatch_widens_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """HSB_AUTH_ALLOW_API_KEY_BACKLOG=1 widens the allowlist for one agent
    so OpenAIProvider can be built from an API key. Without the escape
    hatch, the same env raises AuthResolutionError."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxx")
    # Point CODEX_HOME at an empty tmp dir so the _CodexOAuth2CliToken
    # strategy's detect() returns False (no auth.json there). Otherwise on
    # an operator's dev machine ~/.codex/auth.json may exist and the
    # Codex-OAuth strategy would short-circuit the walk before the API-key
    # branch is considered.
    empty_codex_home = tmp_path / "empty_codex_home"
    empty_codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(empty_codex_home))

    fake_openai = _stub_openai_sdk(async_client=_fake_async_openai_client([]))
    with patch.dict("sys.modules", {"openai": fake_openai}):
        # Escape hatch ON → succeeds with raw OpenAI backend.
        monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", "1")

        from hsb.runtime.resolver import resolve_runtime
        from llm_providers.providers.openai import (
            OpenAIProvider,
            _RawOpenAIBackend,
        )

        handle = resolve_runtime("backlog")
        assert isinstance(handle.provider, OpenAIProvider)
        assert isinstance(handle.provider._backend, _RawOpenAIBackend)

    # Reset registration so the second resolve_runtime call re-runs the
    # provider decorator against a clean registry.
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)

    fake_openai_2 = _stub_openai_sdk(async_client=_fake_async_openai_client([]))
    with patch.dict("sys.modules", {"openai": fake_openai_2}):
        # Re-import the openai provider so its @ProviderRegistry.register
        # decorator runs against the now-empty registry.
        import llm_providers.providers.openai  # noqa: F401

        # Escape hatch OFF → no auth strategy resolves under the default
        # OAuth-only allowlist, so resolve_runtime bubbles AuthResolutionError.
        monkeypatch.delenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", raising=False)

        from hsb.runtime.resolver import resolve_runtime as resolve_runtime_2

        with pytest.raises(AuthResolutionError):
            resolve_runtime_2("backlog")
