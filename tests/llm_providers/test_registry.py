"""ProviderRegistry / AuthRegistry tests — register, get, build, duplicates."""

from __future__ import annotations

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.base import BaseProvider
from llm_providers.errors import ProviderNotFoundError, UnsupportedAuthError
from llm_providers.protocol import Capabilities
from llm_providers.registry import AuthRegistry, ProviderRegistry


@pytest.fixture(autouse=True)
def _isolate_registries(monkeypatch):
    """Each test gets a fresh empty registry to avoid cross-test pollution."""
    monkeypatch.setattr(ProviderRegistry, "_providers", {})
    monkeypatch.setattr(AuthRegistry, "_strategies", {})


def _caps() -> Capabilities:
    return Capabilities(
        supports_mcp=False,
        supports_native_tools=False,
        supports_hooks=False,
        supports_stateful_client=False,
        supports_output_schema=False,
        supports_system_prompt_file=False,
        supports_streaming=False,
    )


def _make_provider(name: str):
    @ProviderRegistry.register(name)
    class _P(BaseProvider):
        pass

    _P.name = name
    _P.capabilities = _caps()
    _P.supported_auth = (ApiKey,)

    async def _q(self, prompt, options):
        from llm_providers.protocol import Message

        yield Message(text="x", is_final=True)

    _P.query = _q
    _P.client = lambda self, options: None  # type: ignore[assignment]
    _P.__abstractmethods__ = frozenset()
    return _P


def test_register_and_get():
    cls = _make_provider("foo")
    assert ProviderRegistry.get("foo") is cls


def test_get_unknown_raises():
    with pytest.raises(ProviderNotFoundError) as exc:
        ProviderRegistry.get("nope")
    assert exc.value.name == "nope"


def test_register_rejects_duplicate():
    _make_provider("foo")
    with pytest.raises(ValueError, match="already registered"):
        _make_provider("foo")


def test_register_rejects_non_baseprovider():
    with pytest.raises(TypeError, match="BaseProvider"):

        @ProviderRegistry.register("nope")
        class _NotAProvider:
            pass


def test_register_rejects_name_mismatch():
    with pytest.raises(ValueError, match="!="):

        @ProviderRegistry.register("foo")
        class _P(BaseProvider):
            name = "bar"  # mismatch
            capabilities = _caps()
            supported_auth = (ApiKey,)

            async def query(self, p, o):
                from llm_providers.protocol import Message

                yield Message(text="", is_final=True)

            def client(self, o):
                return None


def test_register_adopts_decorator_name_when_class_does_not_set_it():
    @ProviderRegistry.register("auto-named")
    class _P(BaseProvider):
        capabilities = _caps()
        supported_auth = (ApiKey,)

        async def query(self, p, o):
            from llm_providers.protocol import Message

            yield Message(text="", is_final=True)

        def client(self, o):
            return None

    assert _P.name == "auto-named"


def test_build_constructs_with_auth():
    _make_provider("foo")
    p = ProviderRegistry.build("foo", auth=ApiKey(api_key="k"))
    assert p.name == "foo"


def test_build_from_settings_delegates_to_factory(monkeypatch):
    """``build_from_settings`` defers to ``resolve_auth`` and constructs the
    provider with the returned strategy."""
    _make_provider("foo")

    sentinel = ApiKey(api_key="resolved-by-factory")

    def _fake_resolve(name, kind):
        assert name == "foo"
        assert kind == "api_key"
        return sentinel

    monkeypatch.setattr("llm_providers.auth.factory.resolve_auth", _fake_resolve)

    p = ProviderRegistry.build_from_settings("foo", auth_kind="api_key")
    assert p._auth is sentinel  # noqa: SLF001


def test_build_rejects_wrong_auth():
    _make_provider("foo")

    class _Other(AuthStrategy):
        kind = "other"

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

    with pytest.raises(UnsupportedAuthError):
        ProviderRegistry.build("foo", auth=_Other())


def test_names_returns_sorted_tuple():
    _make_provider("zeta")
    _make_provider("alpha")
    assert ProviderRegistry.names() == ("alpha", "zeta")


def test_auth_registry_register_and_kinds():
    @AuthRegistry.register("my-kind")
    class _S(AuthStrategy):
        kind = "my-kind"

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

    assert AuthRegistry.get("my-kind") is _S
    assert "my-kind" in AuthRegistry.kinds()


def test_auth_registry_get_unknown_raises():
    with pytest.raises(KeyError, match="not registered"):
        AuthRegistry.get("nope")


def test_auth_registry_rejects_duplicate():
    @AuthRegistry.register("dup")
    class _A(AuthStrategy):
        kind = "dup"

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

    with pytest.raises(ValueError, match="already registered"):

        @AuthRegistry.register("dup")
        class _B(AuthStrategy):  # noqa: F811
            kind = "dup"

            def resolve(self) -> Credential:
                return Credential(kind=self.kind, payload={})


def test_auth_registry_rejects_non_authstrategy():
    with pytest.raises(TypeError, match="AuthStrategy"):

        @AuthRegistry.register("bad")
        class _NotAStrategy:
            kind = "bad"


def test_auth_registry_rejects_kind_mismatch():
    with pytest.raises(ValueError, match="!="):

        @AuthRegistry.register("decorator-kind")
        class _S(AuthStrategy):
            kind = "class-kind"  # mismatch

            def resolve(self) -> Credential:
                return Credential(kind=self.kind, payload={})
