"""Side-effect imports populate ProviderRegistry on package import."""

from __future__ import annotations

import importlib
import sys


def test_provider_registry_populated_after_import_llm_providers(monkeypatch):
    """Reloading llm_providers re-triggers @ProviderRegistry.register decorators.

    The cold-start path is exercised by every other test in this suite (the
    test runner imports llm_providers once); this test verifies the
    side-effect imports remain wired correctly across a reload. We keep
    `llm_providers.registry` cached so ``ProviderRegistry``'s class identity
    survives, then evict the provider/auth subpackages so their bodies
    re-execute and the decorators run against the same class.
    """
    import llm_providers
    from llm_providers.registry import AuthRegistry, ProviderRegistry

    monkeypatch.setattr(ProviderRegistry, "_providers", {})
    # Auth strategies are also self-registering — reset that registry too so
    # the @AuthRegistry.register decorators can re-run when the auth subpackage
    # is reloaded.
    monkeypatch.setattr(AuthRegistry, "_strategies", {})

    # Evict the provider/auth subpackages from sys.modules so their module
    # bodies (and @ProviderRegistry.register decorators) re-execute. We
    # deliberately keep `llm_providers.registry` cached — re-importing it
    # would create a fresh ProviderRegistry class with its own _providers
    # dict, and our reset would be against the orphaned class.
    for mod_name in list(sys.modules):
        if mod_name.startswith("llm_providers.providers") or mod_name.startswith(
            "llm_providers.auth"
        ):
            del sys.modules[mod_name]

    # Also drop the cached `providers`/`auth` attributes on the parent
    # package. Otherwise `from llm_providers import providers` is satisfied
    # by attribute lookup against the still-attached submodule object and
    # never triggers a real import — the decorators never re-run.
    for attr in ("providers", "auth"):
        if hasattr(llm_providers, attr):
            delattr(llm_providers, attr)

    importlib.reload(llm_providers)

    names = ProviderRegistry.names()
    assert "claude" in names
    assert "openai" in names


def test_public_surface_re_exports():
    import llm_providers

    for name in [
        "Capabilities",
        "Message",
        "ProviderOptions",
        "ProviderRegistry",
        "AuthRegistry",
        "auto_resolve_auth",
        "ApiKey",
        "OAuth2CliToken",
        "TextSystemPrompt",
        "SkillReference",
        "PresetSystemPrompt",
        "LLMProvidersError",
        "UnsupportedCapabilityError",
        "UnsupportedAuthError",
        "AuthResolutionError",
        "ProviderNotFoundError",
        "BaseProvider",
        "StatefulClient",
        "ToolPolicy",
        "ToolSpec",
        "McpServerSpec",
    ]:
        assert hasattr(llm_providers, name), f"llm_providers.{name} missing"
