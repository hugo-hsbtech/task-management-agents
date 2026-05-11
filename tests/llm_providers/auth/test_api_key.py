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


def test_default_uses_class_default_env_var(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "x")
    s = ApiKey.default()
    assert s.detect() is True


def test_kind_classvar():
    assert ApiKey.kind == "api_key"
