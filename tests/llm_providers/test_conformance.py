"""Conformance suite — parametrized over every registered provider.

Asserts the Liskov contract: every provider satisfies the same minimal
shape, and providers do not import from hsb (decoupling invariant).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import (
    UnsupportedAuthError,
    UnsupportedCapabilityError,  # noqa: F401  (re-exported for conformance authors)
)
from llm_providers.protocol import Capabilities
from llm_providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _ensure_providers_registered():
    """Other test modules' autouse fixtures pop providers out of the registry
    and evict the provider modules from sys.modules. Re-import them here so
    each conformance test sees a populated registry."""
    import importlib
    import sys

    for mod_name in (
        "llm_providers.providers.claude",
        "llm_providers.providers.gemini",
        "llm_providers.providers.openai",
    ):
        if mod_name not in sys.modules:
            importlib.import_module(mod_name)
    yield


@pytest.fixture(scope="module")
def provider_names() -> list[str]:
    """All registered providers — populated by the side-effect imports."""
    import llm_providers  # noqa: F401  (ensure registration happens)

    return list(ProviderRegistry.names())


@pytest.fixture
def provider_cls(request):
    """Resolve a provider class by parametrized name."""
    return ProviderRegistry.get(request.param)


@pytest.mark.parametrize("name", ["claude", "gemini", "openai"])
class TestProviderConformance:
    """Run the same assertions against every registered provider."""

    def test_subclasses_base_provider(self, name):
        cls = ProviderRegistry.get(name)
        assert issubclass(cls, BaseProvider)

    def test_name_classvar_matches_registry_key(self, name):
        cls = ProviderRegistry.get(name)
        assert cls.name == name

    def test_capabilities_is_a_Capabilities_instance(self, name):
        cls = ProviderRegistry.get(name)
        # capabilities may be ClassVar OR an instance property — both forms
        # are valid (see spec §7.2 note). The conformance test reads
        # capabilities off the class; if a provider uses @property the
        # ClassVar still has the default placeholder, which is fine.
        caps = getattr(cls, "capabilities", None)
        assert caps is not None
        # When it's a property descriptor, instantiating is needed; we assert
        # the type either way via duck-typing on the bool flags.
        if isinstance(caps, Capabilities):
            assert isinstance(caps.supports_mcp, bool)
        else:
            # It's a property — accept it; capability access happens on
            # instances. Conformance for instance capabilities is covered by
            # provider-specific tests.
            assert isinstance(caps, property)

    def test_supported_auth_is_nonempty_tuple_of_AuthStrategy(self, name):
        cls = ProviderRegistry.get(name)
        assert isinstance(cls.supported_auth, tuple)
        assert len(cls.supported_auth) > 0
        for strat_cls in cls.supported_auth:
            assert issubclass(strat_cls, AuthStrategy)

    def test_unsupported_auth_raises_UnsupportedAuthError(self, name):
        cls = ProviderRegistry.get(name)

        class _NeverSupported(AuthStrategy):
            kind = "_never_supported_in_conformance_tests"

            def detect(self) -> bool:
                return True

            def resolve(self):
                from llm_providers.auth.base import Credential

                return Credential(kind=self.kind, payload={})

            @classmethod
            def default(cls):
                return cls()

        if _NeverSupported in cls.supported_auth:
            pytest.skip("This synthetic strategy is somehow in supported_auth; skip")

        with pytest.raises(UnsupportedAuthError):
            # Construct via __new__ bypass to skip _backend init; we only test
            # _validate_auth here.
            cls._validate_auth(_NeverSupported())

    def test_module_does_not_import_hsb(self, name):
        """Structural assertion: provider modules must not import from hsb.

        Enforced via AST parse, not runtime import, so this fails even when
        hsb is installed."""
        cls = ProviderRegistry.get(name)
        module_path = Path(inspect.getfile(cls))
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("hsb"), (
                    f"{module_path.name} imports from {node.module}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("hsb"), (
                        f"{module_path.name} imports {alias.name}"
                    )


def test_provider_registry_has_at_least_claude_openai_and_gemini():
    import llm_providers  # noqa: F401

    names = ProviderRegistry.names()
    assert "claude" in names
    assert "openai" in names
    assert "gemini" in names
