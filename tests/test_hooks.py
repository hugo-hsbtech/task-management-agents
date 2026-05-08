"""Unit tests for src/hsb/agents/hooks.py — LINR-05 retry behavior + audit log + filter enforcement."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hsb.agents import hooks
from hsb.agents.hooks import (
    MAX_RETRIES,
    _retry_counts,
    enforce_list_filters,
    linear_audit_hook,
    linear_retry_hook,
    pre_compact_handler,
)


@pytest.fixture(autouse=True)
def reset_retry_counts():
    _retry_counts.clear()
    yield
    _retry_counts.clear()


@pytest.mark.asyncio
async def test_retry_backoff_first_attempt():
    """Scenario 7 (Reference Dataset): single transient failure, 1 retry, 1s delay."""
    delays_recorded = []

    async def fake_sleep(delay):
        delays_recorded.append(delay)

    with patch("hsb.agents.hooks.asyncio.sleep", new=fake_sleep):
        result = await linear_retry_hook(
            {"tool_name": "mcp__linear__create_issue"}, "tool-use-1", None
        )
    assert "systemMessage" in result
    assert "attempt 1/3" in result["systemMessage"]
    assert "Waited 1s" in result["systemMessage"]
    assert _retry_counts["tool-use-1"] == 1
    assert delays_recorded == [1.0]


@pytest.mark.asyncio
async def test_retry_backoff_exponential_timing():
    """Verify delays are 1s, 2s, 4s (exponential)."""
    delays_recorded = []

    async def fake_sleep(delay):
        delays_recorded.append(delay)

    with patch("hsb.agents.hooks.asyncio.sleep", new=fake_sleep):
        for _i in range(3):
            await linear_retry_hook(
                {"tool_name": "mcp__linear__create_issue"}, "tool-use-2", None
            )
    assert delays_recorded == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_retry_cap_at_max():
    """Scenario 8: after 3 failures, return 'Do not retry'."""

    async def fake_sleep(delay):
        pass

    with patch("hsb.agents.hooks.asyncio.sleep", new=fake_sleep):
        for _ in range(MAX_RETRIES):
            await linear_retry_hook(
                {"tool_name": "mcp__linear__create_issue"}, "tool-use-3", None
            )
    # 4th call hits the cap
    result = await linear_retry_hook(
        {"tool_name": "mcp__linear__create_issue"}, "tool-use-3", None
    )
    assert "Do not retry" in result["systemMessage"]
    assert "failed after 3 retries" in result["systemMessage"]
    assert "tool-use-3" not in _retry_counts


@pytest.mark.asyncio
async def test_retry_hook_skips_non_linear_tool():
    result = await linear_retry_hook({"tool_name": "Bash"}, "tool-use-4", None)
    assert result == {}
    assert "tool-use-4" not in _retry_counts


@pytest.mark.asyncio
async def test_audit_hook_writes_log_line(tmp_path, monkeypatch):
    log_path = tmp_path / "linear_audit.log"
    monkeypatch.setattr(hooks, "AUDIT_LOG_PATH", str(log_path))

    await linear_audit_hook(
        {
            "tool_name": "mcp__linear__create_issue",
            "tool_output": {"id": "LIN-1", "url": "https://linear.app/x/LIN-1"},
        },
        "tool-use-5",
        None,
    )

    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tool"] == "mcp__linear__create_issue"
    assert entry["tool_use_id"] == "tool-use-5"
    assert "ts" in entry
    assert "tool_output_preview" in entry


@pytest.mark.asyncio
async def test_audit_hook_skips_non_linear_tool(tmp_path, monkeypatch):
    log_path = tmp_path / "linear_audit.log"
    monkeypatch.setattr(hooks, "AUDIT_LOG_PATH", str(log_path))
    await linear_audit_hook({"tool_name": "Bash"}, "x", None)
    assert not log_path.exists()


@pytest.mark.asyncio
async def test_audit_hook_clears_retry_counter(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    _retry_counts["tool-use-6"] = 2
    await linear_audit_hook(
        {"tool_name": "mcp__linear__create_issue", "tool_output": {}},
        "tool-use-6",
        None,
    )
    assert "tool-use-6" not in _retry_counts


@pytest.mark.asyncio
async def test_enforce_list_filters_denies_unfiltered():
    result = await enforce_list_filters(
        {"tool_name": "mcp__linear__list_issues", "tool_input": {}}, None, None
    )
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "teamId or projectId filter"
        in result["hookSpecificOutput"]["permissionDecisionReason"]
    )


@pytest.mark.asyncio
async def test_enforce_list_filters_allows_with_teamId():
    result = await enforce_list_filters(
        {"tool_name": "mcp__linear__list_issues", "tool_input": {"teamId": "T-1"}},
        None,
        None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_enforce_list_filters_allows_with_projectId():
    result = await enforce_list_filters(
        {"tool_name": "mcp__linear__list_issues", "tool_input": {"projectId": "P-1"}},
        None,
        None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_enforce_list_filters_skips_non_list_tool():
    result = await enforce_list_filters(
        {"tool_name": "mcp__linear__create_issue", "tool_input": {}}, None, None
    )
    assert result == {}


@pytest.mark.asyncio
async def test_pre_compact_handler_returns_warning(tmp_path):
    result = await pre_compact_handler({"transcript_path": None}, None, None)
    assert "CONTEXT COMPACTION TRIGGERED" in result["systemMessage"]
    assert "Re-read the current Linear issue state" in result["systemMessage"]


@pytest.mark.asyncio
async def test_pre_compact_handler_archives_transcript(tmp_path, monkeypatch):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"role":"user","content":"hi"}\n')
    # Run from tmp_path so the .claude/ archive lands there
    monkeypatch.chdir(tmp_path)
    Path(".claude").mkdir(exist_ok=True)
    await pre_compact_handler({"transcript_path": str(transcript)}, None, None)
    archives = list(Path(".claude").glob("compaction_archive_*.jsonl"))
    assert len(archives) == 1
