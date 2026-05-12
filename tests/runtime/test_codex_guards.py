"""Tests for Codex-side OAuth and MCP verification helpers."""

from __future__ import annotations

import pytest

from hsb.runtime.codex_guards import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)


def _write_codex(tmp_path, *, config_content: str | None, with_auth_json: bool):
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    if config_content is not None:
        (codex_home / "config.toml").write_text(config_content)
    if with_auth_json:
        (codex_home / "auth.json").write_text("{}")
    return codex_home


def test_oauth_passes_when_config_and_auth_present(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "chatgpt"\nmodel = "gpt-5.4"\n',
        with_auth_json=True,
    )
    parsed = assert_codex_oauth_only(codex_home=home)
    assert parsed["forced_login_method"] == "chatgpt"


def test_oauth_rejects_missing_config(tmp_path):
    home = _write_codex(tmp_path, config_content=None, with_auth_json=True)
    with pytest.raises(RuntimeError, match=r"~/.codex/config.toml"):
        assert_codex_oauth_only(codex_home=home)


def test_oauth_rejects_wrong_login_method(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "api"\n',
        with_auth_json=True,
    )
    with pytest.raises(RuntimeError, match=r'forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=home)


def test_oauth_rejects_missing_auth_json(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "chatgpt"\n',
        with_auth_json=False,
    )
    with pytest.raises(RuntimeError, match=r"codex login --device-auth"):
        assert_codex_oauth_only(codex_home=home)


def test_verify_mcp_passes_when_all_present():
    parsed = {"mcp_servers": {"linear": {"command": "npx"}, "github": {"command": "x"}}}
    verify_codex_mcp(parsed, ["linear", "github"])  # no raise


def test_verify_mcp_rejects_missing_block():
    parsed = {"mcp_servers": {"linear": {"command": "npx"}}}
    with pytest.raises(RuntimeError, match=r"github"):
        verify_codex_mcp(parsed, ["linear", "github"])


def test_verify_mcp_handles_empty_section():
    parsed: dict = {}
    with pytest.raises(RuntimeError, match=r"linear"):
        verify_codex_mcp(parsed, ["linear"])


# ---------------------------------------------------------------------------
# Coverage-gap test: line 26
# ---------------------------------------------------------------------------


def test_resolve_codex_home_fallback_to_home_dot_codex(monkeypatch):
    """Line 26: when codex_home arg is None and CODEX_HOME env is unset,
    _resolve_codex_home returns Path.home() / '.codex'."""
    from pathlib import Path

    from hsb.runtime.codex_guards import _resolve_codex_home

    monkeypatch.delenv("CODEX_HOME", raising=False)
    result = _resolve_codex_home(None)
    assert result == Path.home() / ".codex"
