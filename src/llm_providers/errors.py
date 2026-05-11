"""Exception hierarchy for the llm_providers library.

Library raises only LLMProvidersError subclasses. SDK exceptions are
wrapped in ProviderRuntimeError with __cause__ set to the original.
"""

from __future__ import annotations


class LLMProvidersError(Exception):
    """Root of all library-defined errors."""


class ProviderNotFoundError(LLMProvidersError):
    """Raised when ProviderRegistry.get(name) is called for an unregistered name."""

    def __init__(self, name: str, available: tuple[str, ...]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Provider {name!r} is not registered. Available providers: {available}."
        )


class UnsupportedAuthError(LLMProvidersError):
    """Caller passed an AuthStrategy not declared in provider.supported_auth."""

    def __init__(self, provider: str, got: str, accepted: list[str]) -> None:
        self.provider = provider
        self.got = got
        self.accepted = accepted
        super().__init__(
            f"Provider {provider!r} does not accept auth strategy {got!r}. "
            f"Accepted: {accepted}."
        )


class UnsupportedCapabilityError(LLMProvidersError):
    """Caller exercised a feature the provider does not expose."""

    def __init__(self, provider: str, capability: str) -> None:
        self.provider = provider
        self.capability = capability
        super().__init__(
            f"Provider {provider!r} does not support capability {capability!r}."
        )


class AuthResolutionError(LLMProvidersError):
    """auto_resolve_auth exhausted provider.supported_auth without a match."""

    def __init__(
        self,
        provider: str,
        skipped: list[tuple[str, str]],
        accepted: set[str] | None,
    ) -> None:
        self.provider = provider
        self.skipped = skipped
        self.accepted = accepted
        detail = "; ".join(f"{name}: {reason}" for name, reason in skipped)
        super().__init__(
            f"Could not resolve any auth strategy for provider {provider!r}. "
            f"Accepted kinds: {accepted}. Tried: [{detail}]."
        )


class AuthDetectionFailed(LLMProvidersError):
    """Strategy.detect() returned True but resolve() then failed.

    Raised by an AuthStrategy.resolve() so auto_resolve_auth can record it
    and continue the walk instead of bubbling."""


class CredentialMismatch(LLMProvidersError):
    """Provider received a Credential whose kind it doesn't know how to apply.

    Defense-in-depth against AuthStrategy/Provider drift."""


class TranslationError(LLMProvidersError):
    """A _translate_* hook produced an invalid native option object."""


class ProviderRuntimeError(LLMProvidersError):
    """Wraps an SDK exception raised during query()/client().

    The original SDK exception is on __cause__."""

    def __init__(self, provider: str, phase: str) -> None:
        self.provider = provider
        self.phase = phase
        super().__init__(
            f"Provider {provider!r} raised during {phase!r}. See __cause__ for details."
        )
