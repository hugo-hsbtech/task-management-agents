"""Per-agent runtime selection via env var."""

from __future__ import annotations

import pytest

from hsb.runtime.claude import ClaudeRuntime


def _patch_codex_home(monkeypatch, tmp_path):
    """Set CODEX_HOME to a valid fixture so CodexRuntime construction passes."""
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\n[mcp_servers.linear]\ncommand="npx"\n'
    )
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(home))


def test_default_returns_claude(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_BACKLOG", raising=False)
    from hsb.agents._sdk_options import resolve_runtime

    rt = resolve_runtime("backlog")
    assert isinstance(rt, ClaudeRuntime)


def test_codex_value_returns_codex_runtime(monkeypatch, tmp_path):
    _patch_codex_home(monkeypatch, tmp_path)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    from hsb.agents._sdk_options import resolve_runtime
    from hsb.runtime.codex import CodexRuntime

    rt = resolve_runtime("backlog")
    assert isinstance(rt, CodexRuntime)


def test_unknown_value_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "gpt-3")
    from hsb.agents._sdk_options import resolve_runtime

    with pytest.raises(ValueError, match=r"HSB_RUNTIME_BACKLOG"):
        resolve_runtime("backlog")


def test_wio_codex_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_WIO", "codex")
    from hsb.agents._sdk_options import resolve_runtime

    with pytest.raises(ValueError, match=r"WIO"):
        resolve_runtime("wio")


def test_agent_name_normalized_to_upper(monkeypatch):
    """resolve_runtime("backlog") reads HSB_RUNTIME_BACKLOG."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")
    from hsb.agents._sdk_options import resolve_runtime

    rt = resolve_runtime("backlog")
    assert rt.name == "claude"
