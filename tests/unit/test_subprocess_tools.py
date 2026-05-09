"""Tests for src/hsb/agents/subprocess_tools.py.

These tests mock asyncio.create_subprocess_exec to avoid actually running
git/gh/pytest commands.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.agents import subprocess_tools as st


@pytest.fixture
def mock_subprocess():
    """Mock asyncio.create_subprocess_exec to return a fake process."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"stdout-output", b"stderr-output"))
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ) as mock_exec:
        yield mock_exec


@pytest.mark.asyncio
async def test_run_cmd_returns_combined_output(mock_subprocess):
    result = await st._run_cmd(["echo", "hello"])
    assert "stdout-output" in result
    assert "stderr-output" in result


@pytest.mark.asyncio
async def test_git_checkout(mock_subprocess):
    await st.git_checkout("feature/x")
    args = mock_subprocess.call_args[0]
    assert args == ("git", "checkout", "feature/x")


@pytest.mark.asyncio
async def test_git_push_force_with_lease(mock_subprocess):
    await st.git_push_force_with_lease("feature/x")
    args = mock_subprocess.call_args[0]
    assert "--force-with-lease" in args
    assert "feature/x" in args


@pytest.mark.asyncio
async def test_git_rebase(mock_subprocess):
    await st.git_rebase("epic/main", "old-tip", "feature/x")
    args = mock_subprocess.call_args[0]
    assert "rebase" in args
    assert "--onto" in args


@pytest.mark.asyncio
async def test_git_fetch(mock_subprocess):
    await st.git_fetch()
    args = mock_subprocess.call_args[0]
    assert args == ("git", "fetch", "origin")


@pytest.mark.asyncio
async def test_git_log(mock_subprocess):
    await st.git_log()
    args = mock_subprocess.call_args[0]
    assert "log" in args


@pytest.mark.asyncio
async def test_git_status(mock_subprocess):
    await st.git_status()
    args = mock_subprocess.call_args[0]
    assert args == ("git", "status")


@pytest.mark.asyncio
async def test_git_add(mock_subprocess):
    await st.git_add("path/file.py")
    args = mock_subprocess.call_args[0]
    assert "add" in args
    assert "path/file.py" in args


@pytest.mark.asyncio
async def test_git_commit(mock_subprocess):
    await st.git_commit("commit message")
    args = mock_subprocess.call_args[0]
    assert "commit" in args
    assert "-m" in args


@pytest.mark.asyncio
async def test_gh_pr_create(mock_subprocess):
    await st.gh_pr_create("title", "body", "main", "feature/x")
    args = mock_subprocess.call_args[0]
    assert "pr" in args and "create" in args


@pytest.mark.asyncio
async def test_gh_pr_list_includes_limit_100(mock_subprocess):
    """Pitfall 4: --limit 100 prevents pagination truncation."""
    await st.gh_pr_list("epic/main")
    args = mock_subprocess.call_args[0]
    assert "100" in args


@pytest.mark.asyncio
async def test_gh_pr_view(mock_subprocess):
    await st.gh_pr_view("42")
    args = mock_subprocess.call_args[0]
    assert "42" in args


@pytest.mark.asyncio
async def test_gh_pr_diff(mock_subprocess):
    await st.gh_pr_diff("42")
    args = mock_subprocess.call_args[0]
    assert "diff" in args


@pytest.mark.asyncio
async def test_run_pytest(mock_subprocess):
    await st.run_pytest("-x --tb=short")
    args = mock_subprocess.call_args[0]
    assert "pytest" in args
    assert "-x" in args


@pytest.mark.asyncio
async def test_run_pytest_no_args(mock_subprocess):
    await st.run_pytest()
    args = mock_subprocess.call_args[0]
    assert "pytest" in args


@pytest.mark.asyncio
async def test_run_ruff(mock_subprocess):
    await st.run_ruff()
    args = mock_subprocess.call_args[0]
    assert args[0] == "ruff"


@pytest.mark.asyncio
async def test_run_mypy(mock_subprocess):
    await st.run_mypy()
    args = mock_subprocess.call_args[0]
    assert args[0] == "mypy"
