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
    """The requested (provider, auth_kind) credential isn't configured.

    Raised by :func:`llm_providers.auth.factory.resolve_auth` when the env
    var or file backing the requested combo is missing. The message names
    exactly which source the operator must populate.
    """


class AuthDetectionFailed(LLMProvidersError):
    """Reserved for future use — currently unraised after the strict-direct
    factory refactor removed the walk-and-detect lifecycle."""


class CredentialMismatch(LLMProvidersError):
    """Provider received a Credential whose kind it doesn't know how to apply.

    Defense-in-depth against AuthStrategy/Provider drift."""


class TranslationError(LLMProvidersError):
    """A _translate_* hook produced an invalid native option object."""


class ProviderRuntimeError(LLMProvidersError):
    """Wraps an SDK exception raised during query()/client().

    The original SDK exception is on __cause__."""

    def __init__(self, provider: str, phase: str, message: str | None = None) -> None:
        self.provider = provider
        self.phase = phase
        msg = (
            message
            or f"Provider {provider!r} raised during {phase!r}. See __cause__ for details."
        )
        super().__init__(msg)


class ClaudeRateLimitError(ProviderRuntimeError):
    """Claude Code CLI hit rate limit (free tier or usage cap)."""

    def __init__(self, reset_time: str | None = None) -> None:
        self.reset_time = reset_time
        msg = "Claude Code rate limit reached"
        if reset_time:
            msg += f" (resets at {reset_time})"
        msg += ". Use CLAUDE_CODE_OAUTH_TOKEN with a paid plan or wait for reset."
        super().__init__("claude", "query", msg)


class ClaudeAuthError(ProviderRuntimeError):
    """Claude Code CLI authentication failed (missing/invalid token)."""

    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason
        msg = "Claude Code authentication failed"
        if reason:
            msg += f": {reason}"
        msg += ". Set CLAUDE_CODE_OAUTH_TOKEN or run 'claude login'."
        super().__init__("claude", "auth", msg)
