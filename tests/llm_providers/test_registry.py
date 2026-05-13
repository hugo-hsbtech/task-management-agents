"""Provider/Auth registry tests — register, get, build, build_auto, duplicates."""

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


def test_build_constructs_with_auth():
    _make_provider("foo")
    # ApiKey.default() raises by design; tests construct explicitly.
    p = ProviderRegistry.build("foo", auth=ApiKey(api_key="k", source="test"))
    assert p.name == "foo"


def test_build_rejects_wrong_auth():
    _make_provider("foo")

    class _Other(AuthStrategy):
        kind = "other"

        def detect(self) -> bool:
            return True

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls):
            return cls()

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

        def detect(self) -> bool:
            return True

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls):
            return cls()

    assert AuthRegistry.get("my-kind") is _S
    assert "my-kind" in AuthRegistry.kinds()


def test_auth_registry_rejects_duplicate():
    @AuthRegistry.register("dup")
    class _A(AuthStrategy):
        kind = "dup"

        def detect(self) -> bool:
            return False

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls):
            return cls()

    with pytest.raises(ValueError, match="already registered"):

        @AuthRegistry.register("dup")
        class _B(AuthStrategy):  # noqa: F811
            kind = "dup"

            def detect(self) -> bool:
                return False

            def resolve(self) -> Credential:
                return Credential(kind=self.kind, payload={})

            @classmethod
            def default(cls):
                return cls()
