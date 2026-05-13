"""Branch-coverage tests for OpenAIProvider — translation, MCP, client raises,
subprocess-backed Codex query path, and CredentialMismatch."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import (
    CredentialMismatch,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedCapabilityError,
)
from llm_providers.prompt import PresetSystemPrompt, TextSystemPrompt
from llm_providers.protocol import ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


@pytest.fixture(autouse=True)
def _isolate_openai_registration():
    """Mirror the pattern in test_openai.py for clean re-import."""
    import sys

    original_module = sys.modules.get("llm_providers.providers.openai")
    original_provider = ProviderRegistry._providers.get("openai")
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)
    yield
    sys.modules.pop("llm_providers.providers.openai", None)
    ProviderRegistry._providers.pop("openai", None)
    if original_module is not None:
        sys.modules["llm_providers.providers.openai"] = original_module
    if original_provider is not None:
        ProviderRegistry._providers["openai"] = original_provider


def _stub_openai_sdk() -> SimpleNamespace:
    return SimpleNamespace(AsyncOpenAI=MagicMock(return_value=MagicMock()))


# ---------------------------------------------------------------------------
# CredentialMismatch — auth that resolves to an unsupported kind
# ---------------------------------------------------------------------------


def test_credential_mismatch_for_unsupported_kind(monkeypatch):
    class _AdcStrategy(AuthStrategy):
        kind = "oauth2_adc"

        def resolve(self) -> Credential:
            return Credential(kind="oauth2_adc", payload={})

    # Force the supported_auth check by name-MRO to include the kind so we
    # reach the resolve branch where CredentialMismatch fires.
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        # Patch supported_auth to whitelist the test strategy class by name
        # without touching the real class identity.
        monkeypatch.setattr(
            OpenAIProvider,
            "supported_auth",
            (_AdcStrategy, *OpenAIProvider.supported_auth),
        )
        with pytest.raises(CredentialMismatch, match="oauth2_adc"):
            OpenAIProvider(auth=_AdcStrategy())


# ---------------------------------------------------------------------------
# Translation hooks — preset, unknown subtype, mcp delegation
# ---------------------------------------------------------------------------


def _build_raw_provider(monkeypatch):
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        return OpenAIProvider(auth=ApiKey(api_key="sk-abc"))


def test_preset_systemprompt_raises_unsupported(monkeypatch):
    provider = _build_raw_provider(monkeypatch)
    with pytest.raises(UnsupportedCapabilityError, match="system_prompt_file"):
        provider._translate_system_prompt(PresetSystemPrompt(preset_id="p"))


def test_unknown_systemprompt_subtype_raises(monkeypatch):
    provider = _build_raw_provider(monkeypatch)

    class _Bogus:
        pass

    with pytest.raises(TranslationError, match="Unknown SystemPrompt"):
        provider._translate_system_prompt(_Bogus())  # type: ignore[arg-type]


def test_skill_reference_reads_file(monkeypatch, tmp_path):
    from llm_providers.prompt import SkillReference

    provider = _build_raw_provider(monkeypatch)
    f = tmp_path / "skill.md"
    f.write_text("content")
    assert provider._translate_system_prompt(SkillReference(path=f)) == "content"


def test_translate_tools_delegates_to_policy(monkeypatch):
    provider = _build_raw_provider(monkeypatch)
    assert provider._translate_tools(ToolPolicy(allowed=("Read",))) == {
        "allowed_tools": ["Read"]
    }


def test_raw_backend_translate_mcp_raises_when_servers_present(monkeypatch):
    provider = _build_raw_provider(monkeypatch)
    spec = McpServerSpec(name="x", transport="stdio", command=("a",))
    with pytest.raises(UnsupportedCapabilityError, match="mcp"):
        provider._translate_mcp((spec,))


def test_raw_backend_translate_mcp_empty_returns_none(monkeypatch):
    provider = _build_raw_provider(monkeypatch)
    assert provider._translate_mcp(()) is None


def test_raw_backend_client_raises(monkeypatch):
    provider = _build_raw_provider(monkeypatch)
    with pytest.raises(UnsupportedCapabilityError, match="raw OpenAI backend"):
        provider.client(_opts())


# ---------------------------------------------------------------------------
# OpenAIProvider.query — non-ProviderRuntimeError wrap
# ---------------------------------------------------------------------------


def test_query_wraps_non_provider_runtime_error(monkeypatch):
    """A backend that raises a plain RuntimeError must surface as ProviderRuntimeError."""
    provider = _build_raw_provider(monkeypatch)

    async def _backend_query(*_a, **_kw):
        raise RuntimeError("boom")
        yield  # pragma: no cover - async-generator marker

    monkeypatch.setattr(provider._backend, "query", _backend_query)

    async def _run():
        async for _ in provider.query("hi", _opts()):
            pass  # pragma: no cover

    with pytest.raises(ProviderRuntimeError, match="query"):
        asyncio.run(_run())


def test_query_passes_provider_runtime_error_through(monkeypatch):
    """If the backend already raises ProviderRuntimeError, don't double-wrap."""
    provider = _build_raw_provider(monkeypatch)

    sentinel = ProviderRuntimeError(provider="openai", phase="query", message="orig")

    async def _backend_query(*_a, **_kw):
        raise sentinel
        yield  # pragma: no cover

    monkeypatch.setattr(provider._backend, "query", _backend_query)

    async def _run():
        async for _ in provider.query("hi", _opts()):
            pass  # pragma: no cover

    with pytest.raises(ProviderRuntimeError) as exc:
        asyncio.run(_run())
    assert exc.value is sentinel


# ---------------------------------------------------------------------------
# _RawOpenAIBackend.query — exception during create()
# ---------------------------------------------------------------------------


def test_raw_backend_query_wraps_create_failure(monkeypatch):
    """openai SDK raising during create() must surface as ProviderRuntimeError."""
    fake_create = AsyncMock(side_effect=RuntimeError("rate limit"))
    fake_completions = SimpleNamespace(create=fake_create)
    fake_chat = SimpleNamespace(completions=fake_completions)
    fake_async_client = SimpleNamespace(chat=fake_chat)
    fake_openai = SimpleNamespace(AsyncOpenAI=MagicMock(return_value=fake_async_client))

    with patch.dict("sys.modules", {"openai": fake_openai}):
        from llm_providers.providers.openai import OpenAIProvider

        provider = OpenAIProvider(auth=ApiKey(api_key="sk-abc"))

        async def _run():
            async for _ in provider.query("hi", _opts()):
                pass  # pragma: no cover

        with pytest.raises(ProviderRuntimeError, match="query"):
            asyncio.run(_run())


# ---------------------------------------------------------------------------
# _CodexBackend — translate_mcp dict construction, client() raise, query
# subprocess success and failure paths
# ---------------------------------------------------------------------------


def _codex_home_fixture(monkeypatch, tmp_path) -> Path:
    """Set up a working ~/.codex containing both config.toml and auth.json."""
    (tmp_path / "config.toml").write_text(
        'forced_login_method = "chatgpt"\n[mcp_servers.linear]\ncommand = "x"\n'
    )
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    return tmp_path


def _build_codex_provider(monkeypatch, tmp_path):
    _codex_home_fixture(monkeypatch, tmp_path)
    sdks = {"openai_codex_sdk": SimpleNamespace()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider

        return OpenAIProvider(auth=OAuth2CliToken(token="tok"))


def test_codex_backend_translate_mcp_returns_resolved_blocks(monkeypatch, tmp_path):
    provider = _build_codex_provider(monkeypatch, tmp_path)
    spec = McpServerSpec(name="linear", transport="stdio", command=("x",))
    out = provider._translate_mcp((spec,))
    assert "linear" in out


def test_codex_backend_client_raises(monkeypatch, tmp_path):
    provider = _build_codex_provider(monkeypatch, tmp_path)
    with pytest.raises(UnsupportedCapabilityError, match="Codex backend"):
        provider.client(_opts())


@pytest.mark.asyncio
async def test_codex_backend_query_verifies_mcp_servers_before_running(
    monkeypatch, tmp_path
):
    """Branch: when options.mcp_servers is non-empty, verify_codex_mcp runs first.
    Pass a server name absent from config.toml to force the verification error."""
    provider = _build_codex_provider(monkeypatch, tmp_path)
    spec = McpServerSpec(name="not-configured", transport="stdio", command=("x",))
    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="x"),
        model="gpt-4o",
        max_turns=1,
        tool_policy=ToolPolicy(),
        mcp_servers=(spec,),
    )
    # The CodexBackend raises RuntimeError; OpenAIProvider wraps it.
    with pytest.raises(ProviderRuntimeError) as exc:
        async for _ in provider.query("hi", opts):
            pass  # pragma: no cover
    assert "mcp_servers" in str(exc.value.__cause__)


@pytest.mark.asyncio
async def test_codex_backend_query_subprocess_success(monkeypatch, tmp_path):
    """End-to-end success path for the Codex subprocess query."""
    provider = _build_codex_provider(monkeypatch, tmp_path)

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.stdin.write = MagicMock()
    fake_proc.stdin.close = MagicMock()
    fake_proc.returncode = 0

    async def _stdout_iter():
        for line in (b"chunk-1\n", b"chunk-2\n"):
            yield line

    fake_proc.stdout = _stdout_iter()
    fake_proc.stderr = MagicMock()
    fake_proc.stderr.read = AsyncMock(return_value=b"")
    fake_proc.wait = AsyncMock(return_value=0)

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=fake_proc),
    )

    msgs = []
    async for m in provider.query(
        "hi",
        ProviderOptions(
            system_prompt=TextSystemPrompt(text="be helpful"),
            model="gpt-4o",
            max_turns=3,
            tool_policy=ToolPolicy(),
            cwd="/work",
        ),
    ):
        msgs.append(m)

    assert msgs[-1].is_final
    assert "chunk-1" in msgs[-1].text


@pytest.mark.asyncio
async def test_codex_backend_query_nonzero_exit_raises(monkeypatch, tmp_path):
    provider = _build_codex_provider(monkeypatch, tmp_path)

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.returncode = 1

    async def _empty():
        return
        yield  # pragma: no cover

    fake_proc.stdout = _empty()
    fake_proc.stderr = MagicMock()
    fake_proc.stderr.read = AsyncMock(return_value=b"x" * 600)  # >500 → truncation path
    fake_proc.wait = AsyncMock(return_value=1)

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=fake_proc),
    )

    # The CodexBackend raises RuntimeError; the OpenAIProvider wrapper
    # re-raises as ProviderRuntimeError. Confirm both layers are reachable
    # via __cause__.
    with pytest.raises(ProviderRuntimeError) as exc:
        async for _ in provider.query("hi", _opts()):
            pass  # pragma: no cover
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "Codex CLI failed" in str(exc.value.__cause__)


@pytest.mark.asyncio
async def test_codex_backend_query_unmapped_permission_mode_raises(
    monkeypatch, tmp_path
):
    provider = _build_codex_provider(monkeypatch, tmp_path)

    bad_opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="x"),
        model="gpt-4o",
        max_turns=1,
        tool_policy=ToolPolicy(),
        permission_mode="bogus",  # type: ignore[arg-type]
    )
    # UnsupportedCapabilityError raised inside the backend gets wrapped by
    # OpenAIProvider.query into ProviderRuntimeError; check the cause.
    with pytest.raises(ProviderRuntimeError) as exc:
        async for _ in provider.query("hi", bad_opts):
            pass  # pragma: no cover
    assert isinstance(exc.value.__cause__, UnsupportedCapabilityError)


def _opts() -> ProviderOptions:
    return ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="gpt-4o",
        max_turns=3,
        tool_policy=ToolPolicy(),
    )
