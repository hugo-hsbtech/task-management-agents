"""Tests for src/hsb/agents/filesystem_tools.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from hsb.agents.filesystem_tools import (
    edit_file,
    glob_files,
    grep_files,
    read_file,
    write_file,
)


@pytest.mark.asyncio
async def test_read_file_returns_contents(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("hello world", encoding="utf-8")
    result = await read_file(str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_glob_files_returns_sorted(tmp_path: Path):
    (tmp_path / "b.py").write_text("")
    (tmp_path / "a.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    result = await glob_files(str(tmp_path / "*.py"))
    assert len(result) == 2
    assert result == sorted(result)


@pytest.mark.asyncio
async def test_glob_files_recursive(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "x.py").write_text("")
    (tmp_path / "y.py").write_text("")
    result = await glob_files(str(tmp_path / "**" / "*.py"))
    assert len(result) >= 2


@pytest.mark.asyncio
async def test_grep_files_finds_pattern(tmp_path: Path):
    f = tmp_path / "data.txt"
    f.write_text("hello\nworld\nhello again\n")
    result = await grep_files(r"hello", str(tmp_path))
    assert any("hello" in r for r in result)
    assert any("hello again" in r for r in result)


@pytest.mark.asyncio
async def test_grep_files_handles_unreadable(tmp_path: Path):
    """grep_files swallows IsADirectoryError/PermissionError gracefully."""
    sub = tmp_path / "sub"
    sub.mkdir()
    result = await grep_files("anything", str(tmp_path))
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_grep_files_non_recursive(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("findme\n")
    result = await grep_files("findme", str(tmp_path), recursive=False)
    assert any("findme" in r for r in result)


@pytest.mark.asyncio
async def test_write_file_creates_parents(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    msg = await write_file(str(target), "content")
    assert target.read_text() == "content"
    assert "Wrote" in msg


@pytest.mark.asyncio
async def test_edit_file_replaces_first_occurrence(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("foo bar foo baz")
    msg = await edit_file(str(f), "foo", "qux")
    assert f.read_text() == "qux bar foo baz"  # only first
    assert "Edited" in msg


@pytest.mark.asyncio
async def test_edit_file_returns_no_match(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("hello")
    msg = await edit_file(str(f), "absent", "qux")
    assert "No match" in msg
    assert f.read_text() == "hello"  # unchanged
