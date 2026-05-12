"""Error hierarchy and attribute tests."""

from llm_providers.errors import (
    AuthDetectionFailed,
    AuthResolutionError,
    CredentialMismatch,
    LLMProvidersError,
    ProviderNotFoundError,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedAuthError,
    UnsupportedCapabilityError,
)


def test_all_errors_subclass_root():
    for cls in (
        ProviderNotFoundError,
        UnsupportedAuthError,
        UnsupportedCapabilityError,
        AuthResolutionError,
        AuthDetectionFailed,
        CredentialMismatch,
        TranslationError,
        ProviderRuntimeError,
    ):
        assert issubclass(cls, LLMProvidersError)


def test_provider_not_found_error_attrs():
    err = ProviderNotFoundError(name="nope", available=("claude", "openai"))
    assert err.name == "nope"
    assert err.available == ("claude", "openai")
    assert "nope" in str(err)
    assert "claude" in str(err)


def test_unsupported_auth_error_attrs():
    err = UnsupportedAuthError(
        provider="claude", got="OAuth2Adc", accepted=["OAuth2CliToken", "ApiKey"]
    )
    assert err.provider == "claude"
    assert err.got == "OAuth2Adc"
    assert err.accepted == ["OAuth2CliToken", "ApiKey"]


def test_unsupported_capability_error_attrs():
    err = UnsupportedCapabilityError(provider="gemini", capability="mcp")
    assert err.provider == "gemini"
    assert err.capability == "mcp"
    assert "gemini" in str(err) and "mcp" in str(err)


def test_auth_resolution_error_attrs():
    err = AuthResolutionError(
        provider="gemini",
        skipped=[
            ("OAuth2CliToken", "not_detected"),
            ("ApiKey", "filtered_by_accepted_kinds"),
        ],
        accepted={"oauth2_adc"},
    )
    assert err.provider == "gemini"
    assert len(err.skipped) == 2
    assert err.accepted == {"oauth2_adc"}


def test_provider_runtime_error_carries_cause():
    inner = ValueError("sdk blew up")
    err = ProviderRuntimeError(provider="claude", phase="query")
    try:
        raise err from inner
    except ProviderRuntimeError as caught:
        assert caught.__cause__ is inner
        assert caught.provider == "claude"
        assert caught.phase == "query"
