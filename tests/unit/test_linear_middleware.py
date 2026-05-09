"""Tests for src/hsb/agents/linear_middleware.py — replaces old test_hooks.py.

PydanticAI doesn't have HookMatcher; retry/audit behavior is now Python helpers
plus MCPServerStdio toolset configuration.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hsb.agents.linear_middleware import (
    AUDIT_LOG_PATH,
    MAX_RETRIES,
    make_linear_mcp_toolset,
    write_audit_entry,
)


def test_max_retries_constant():
    """MAX_RETRIES preserved at 3 for retry-cap structural tests."""
    assert MAX_RETRIES == 3


def test_audit_log_path_constant():
    """AUDIT_LOG_PATH points to .claude/linear_audit.log."""
    assert AUDIT_LOG_PATH == ".claude/linear_audit.log"


def test_write_audit_entry_creates_json_line(tmp_path, monkeypatch):
    """write_audit_entry appends a JSON line to AUDIT_LOG_PATH."""
    log_file = tmp_path / "audit.log"
    monkeypatch.setattr("hsb.agents.linear_middleware.AUDIT_LOG_PATH", str(log_file))

    write_audit_entry(
        tool_name="mcp__linear__create_issue",
        tool_use_id="tu_123",
        output_preview="ok",
    )

    content = log_file.read_text().strip()
    entry = json.loads(content)
    assert entry["tool"] == "mcp__linear__create_issue"
    assert entry["tool_use_id"] == "tu_123"
    assert entry["tool_output_preview"] == "ok"
    assert "ts" in entry


def test_write_audit_entry_truncates_long_output(tmp_path, monkeypatch):
    """Output preview is truncated to 2000 chars."""
    log_file = tmp_path / "audit.log"
    monkeypatch.setattr("hsb.agents.linear_middleware.AUDIT_LOG_PATH", str(log_file))

    long_output = "x" * 5000
    write_audit_entry("tool", "tu_1", long_output)

    entry = json.loads(log_file.read_text().strip())
    assert len(entry["tool_output_preview"]) == 2000


def test_make_linear_mcp_toolset_returns_mcp_server():
    """make_linear_mcp_toolset returns an MCPServerStdio instance."""
    toolset = make_linear_mcp_toolset()
    # Just check it's not None and has expected attributes
    assert toolset is not None
    # MCPServerStdio has command/args attributes
    assert hasattr(toolset, "command") or hasattr(toolset, "_command") or hasattr(toolset, "_server")
