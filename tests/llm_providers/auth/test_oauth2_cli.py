"""OAuth2CliToken strategy: typed value holder + Credential resolution."""

from __future__ import annotations

import pytest

from llm_providers.auth.oauth2_cli import OAuth2CliToken


def test_construction_with_explicit_token():
    s = OAuth2CliToken(token="tok-xyz")
    cred = s.resolve()
    assert cred.kind == "oauth2_cli_token"
    assert cred.payload["token"] == "tok-xyz"
    assert cred.payload["source"] == "settings"


def test_empty_token_rejected():
    with pytest.raises(ValueError, match="non-empty token"):
        OAuth2CliToken(token="")


def test_kind_classvar():
    assert OAuth2CliToken.kind == "oauth2_cli_token"
