"""auto_resolve_auth walk + accepted_kinds filter."""

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider
from llm_providers.errors import AuthResolutionError
from llm_providers.protocol import Capabilities
from llm_providers.registry import ProviderRegistry, auto_resolve_auth


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "_providers", {})


def _register_provider(name: str, supported_auth):
    @ProviderRegistry.register(name)
    class _P(BaseProvider):
        pass

    _P.name = name
    _P.capabilities = Capabilities(
        supports_mcp=False,
        supports_native_tools=False,
        supports_hooks=False,
        supports_stateful_client=False,
        supports_output_schema=False,
        supports_system_prompt_file=False,
        supports_streaming=False,
    )
    _P.supported_auth = supported_auth

    async def _q(self, p, o):
        from llm_providers.protocol import Message

        yield Message(text="", is_final=True)

    _P.query = _q
    _P.client = lambda self, o: None  # type: ignore[assignment]
    _P.__abstractmethods__ = frozenset()
    return _P


def test_walks_preferred_first_returns_first_detected(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDERS_API_KEY", raising=False)
    monkeypatch.setenv("TOK", "tok-xyz")

    class _PreferredOAuth(OAuth2CliToken):
        @classmethod
        def default(cls):
            return cls(env_var="TOK")

    _register_provider("foo", (_PreferredOAuth, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "oauth2_cli_token"


def test_falls_through_to_second_when_first_not_detected(monkeypatch):
    # Neither OAuth2CliToken default nor API key is wired; use a custom subclass
    class _OAuthNever(OAuth2CliToken):
        @classmethod
        def default(cls):
            return cls()  # no env_var, no path → never detects

    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (_OAuthNever, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "api_key"


def test_accepted_kinds_filters_out_strategies(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (ApiKey,))
    with pytest.raises(AuthResolutionError) as exc:
        auto_resolve_auth("foo", accepted_kinds={"oauth2_cli_token"})
    skipped_names = {name for name, _reason in exc.value.skipped}
    assert "ApiKey" in skipped_names
    assert any("filtered" in reason for _name, reason in exc.value.skipped)


def test_raises_when_no_strategy_detects(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDERS_API_KEY", raising=False)
    _register_provider("foo", (ApiKey,))
    with pytest.raises(AuthResolutionError) as exc:
        auto_resolve_auth("foo")
    assert exc.value.provider == "foo"
    assert any("not_detected" in reason for _name, reason in exc.value.skipped)


def test_construct_failure_is_skipped_not_raised(monkeypatch):
    class _Broken(AuthStrategy):
        kind = "broken"

        def detect(self) -> bool:
            return True

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls):
            raise RuntimeError("construct failed")

    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (_Broken, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "api_key"
