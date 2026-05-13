"""ApiKey strategy: env-var detection + resolution."""

import pytest

from llm_providers.auth.api_key import ApiKey


def test_detect_true_when_env_var_set(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret-value")
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is True


def test_detect_false_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is False


def test_detect_false_when_env_var_empty(monkeypatch):
    monkeypatch.setenv("MY_KEY", "")
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is False


def test_resolve_returns_credential(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret-value")
    s = ApiKey(env_var="MY_KEY")
    cred = s.resolve()
    assert cred.kind == "api_key"
    assert cred.payload["api_key"] == "secret-value"
    assert cred.payload["env_var"] == "MY_KEY"


def test_resolve_raises_when_env_var_absent(monkeypatch):
    from llm_providers.errors import AuthDetectionFailed

    monkeypatch.delenv("MY_KEY", raising=False)
    s = ApiKey(env_var="MY_KEY")
    with pytest.raises(AuthDetectionFailed):
        s.resolve()


def test_default_raises_no_safe_value():
    """ApiKey.default() is intentionally fail-loud — every real provider
    subclasses ApiKey and overrides ``default()`` with its canonical env var."""
    from llm_providers.errors import AuthDetectionFailed

    with pytest.raises(AuthDetectionFailed, match="no value to return"):
        ApiKey.default()


def test_kind_classvar():
    assert ApiKey.kind == "api_key"


def test_init_no_args_raises():
    with pytest.raises(ValueError, match="requires either api_key= or env_var="):
        ApiKey()


def test_detect_true_when_explicit_key():
    s = ApiKey(api_key="sk-test")
    assert s.detect() is True


def test_resolve_returns_credential_for_explicit_key():
    s = ApiKey(api_key="sk-test", source="test")
    cred = s.resolve()
    assert cred.kind == "api_key"
    assert cred.payload["api_key"] == "sk-test"
    assert cred.payload["source"] == "test"


def test_from_auth_creates_api_key():
    from unittest.mock import MagicMock

    from pydantic import SecretStr

    mock_auth = MagicMock()
    mock_auth.key = SecretStr("sk-from-settings")
    s = ApiKey.from_auth(mock_auth)
    assert s.detect() is True
    cred = s.resolve()
    assert cred.payload["api_key"] == "sk-from-settings"
