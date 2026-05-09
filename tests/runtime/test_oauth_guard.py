"""G1 guard now forbids both ANTHROPIC_API_KEY and OPENAI_API_KEY."""
from __future__ import annotations

import pytest

from hsb.agents._sdk_options import assert_oauth2_only


def test_passes_when_neither_var_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert_oauth2_only()  # no raise


def test_rejects_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-foo")
    with pytest.raises(RuntimeError, match=r"G1 violation.*ANTHROPIC_API_KEY"):
        assert_oauth2_only()


def test_rejects_openai_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-foo")
    with pytest.raises(RuntimeError, match=r"G1 violation.*OPENAI_API_KEY"):
        assert_oauth2_only()


def test_rejects_when_both_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    with pytest.raises(RuntimeError, match=r"G1 violation"):
        assert_oauth2_only()
