"""Codex ~/.codex/config.toml parsing + OAuth-only verification.

Ported from tests/runtime/test_codex_guards.py — once Task 16 lands, that
file becomes a re-export shim and these become the canonical tests.
"""

from pathlib import Path

import pytest

from llm_providers.providers._codex_config import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)


def _write_config(home: Path, body: str) -> None:
    (home / "config.toml").write_text(body)


def _write_auth(home: Path) -> None:
    (home / "auth.json").write_text('{"access_token": "x"}')


def test_missing_config_raises(tmp_path):
    with pytest.raises(RuntimeError, match="config.toml not found"):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_missing_forced_login_raises(tmp_path):
    _write_config(tmp_path, "")
    _write_auth(tmp_path)
    with pytest.raises(RuntimeError, match='forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_wrong_forced_login_raises(tmp_path):
    _write_config(tmp_path, 'forced_login_method = "apikey"')
    _write_auth(tmp_path)
    with pytest.raises(RuntimeError, match='forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_missing_auth_json_raises(tmp_path):
    _write_config(tmp_path, 'forced_login_method = "chatgpt"')
    with pytest.raises(RuntimeError, match="auth.json"):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_valid_config_returns_parsed(tmp_path):
    _write_config(
        tmp_path, 'forced_login_method = "chatgpt"\n[mcp_servers.linear]\nurl = "x"'
    )
    _write_auth(tmp_path)
    parsed = assert_codex_oauth_only(codex_home=tmp_path)
    assert parsed["forced_login_method"] == "chatgpt"
    assert "linear" in parsed["mcp_servers"]


def test_verify_codex_mcp_ok():
    parsed = {"mcp_servers": {"linear": {}, "filesystem": {}}}
    verify_codex_mcp(parsed, ["linear"])  # no raise


def test_verify_codex_mcp_missing_raises():
    parsed = {"mcp_servers": {"linear": {}}}
    with pytest.raises(RuntimeError, match="filesystem"):
        verify_codex_mcp(parsed, ["filesystem"])


def test_resolve_codex_home_from_env(monkeypatch, tmp_path):
    """Internal helper honors CODEX_HOME env var."""
    from llm_providers.providers._codex_config import _resolve_codex_home

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert _resolve_codex_home() == tmp_path
