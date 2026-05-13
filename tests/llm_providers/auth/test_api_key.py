"""ApiKey strategy: typed value holder + Credential resolution."""

from __future__ import annotations

import pytest

from llm_providers.auth.api_key import ApiKey


def test_construction_with_explicit_key():
    s = ApiKey(api_key="sk-test")
    cred = s.resolve()
    assert cred.kind == "api_key"
    assert cred.payload["api_key"] == "sk-test"
    assert cred.payload["source"] == "settings"


def test_empty_key_rejected():
    with pytest.raises(ValueError, match="non-empty api_key"):
        ApiKey(api_key="")


def test_kind_classvar():
    assert ApiKey.kind == "api_key"
