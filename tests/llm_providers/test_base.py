"""BaseProvider ABC contract tests."""

from collections.abc import AsyncIterator

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.protocol import Capabilities, Message, ProviderOptions


def _make_caps(**overrides) -> Capabilities:
    defaults = dict(
        supports_mcp=False,
        supports_native_tools=False,
        supports_hooks=False,
        supports_stateful_client=False,
        supports_output_schema=False,
        supports_system_prompt_file=False,
        supports_streaming=False,
    )
    defaults.update(overrides)
    return Capabilities(**defaults)


class _DummyProvider(BaseProvider):
    name = "dummy"
    capabilities = _make_caps(supports_mcp=True)
    supported_auth = (ApiKey,)

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        yield Message(text="ok", is_final=True)

    def client(self, options: ProviderOptions):
        raise NotImplementedError


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        BaseProvider(auth=ApiKey())  # type: ignore[abstract]


def test_subclass_validates_auth_type(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    assert p._auth.kind == "api_key"  # noqa: SLF001


def test_subclass_rejects_unsupported_auth():
    with pytest.raises(UnsupportedAuthError) as exc:
        _DummyProvider(auth=OAuth2CliToken(env_var="X"))
    assert exc.value.provider == "dummy"
    assert exc.value.got == "OAuth2CliToken"
    assert "ApiKey" in exc.value.accepted


def test_require_capability_passes_when_true(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    p.require_capability("mcp")  # supports_mcp=True


def test_require_capability_raises_when_false(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    with pytest.raises(UnsupportedCapabilityError) as exc:
        p.require_capability("hooks")
    assert exc.value.provider == "dummy"
    assert exc.value.capability == "hooks"


def test_translate_hooks_default_to_NotImplementedError(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    with pytest.raises(NotImplementedError):
        p._translate_system_prompt(None)  # type: ignore[arg-type]  # noqa: SLF001
    with pytest.raises(NotImplementedError):
        p._translate_tools(None)  # type: ignore[arg-type]  # noqa: SLF001
    with pytest.raises(NotImplementedError):
        p._translate_mcp(())  # noqa: SLF001
