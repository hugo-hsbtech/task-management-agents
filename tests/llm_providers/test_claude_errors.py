"""Coverage tests for ClaudeRateLimitError / ClaudeAuthError constructors."""

from __future__ import annotations

from llm_providers.errors import ClaudeAuthError, ClaudeRateLimitError


def test_rate_limit_error_with_reset_time():
    err = ClaudeRateLimitError(reset_time="3pm UTC")
    assert err.reset_time == "3pm UTC"
    assert "3pm UTC" in str(err)
    assert err.phase == "query"


def test_rate_limit_error_without_reset_time():
    err = ClaudeRateLimitError()
    assert err.reset_time is None
    assert "rate limit" in str(err).lower()


def test_auth_error_with_reason():
    err = ClaudeAuthError(reason="oauth_token_invalid")
    assert err.reason == "oauth_token_invalid"
    assert "oauth_token_invalid" in str(err)
    assert err.phase == "auth"


def test_auth_error_without_reason():
    err = ClaudeAuthError()
    assert err.reason is None
    assert "authentication failed" in str(err).lower()
