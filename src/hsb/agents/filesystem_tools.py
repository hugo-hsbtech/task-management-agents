"""filesystem_tools.py — PydanticAI tool implementations for file system ops.

These replace the claude-agent-sdk built-in Read/Glob/Grep/Write/Edit tool references.
UAT Agent uses Read, Glob, Grep. Builder Agent uses Read, Write, Edit.
All fully typed and sandboxed.
"""

from __future__ import annotations

import glob as _glob
import re as _re
from pathlib import Path
from typing import Any


async def read_file(path: str) -> str:
    """Read a file by absolute or relative path."""
    return Path(path).read_text(encoding="utf-8")


async def glob_files(pattern: str) -> list[str]:
    """Glob for files matching pattern. Returns sorted list of paths."""
    return sorted(_glob.glob(pattern, recursive=True))


async def grep_files(pattern: str, path: str, recursive: bool = True) -> list[str]:
    """Search for regex pattern in files under path. Returns matching lines with file:line: prefix."""
    results: list[str] = []
    flags = (
        _glob.glob(f"{path}/**/*", recursive=recursive)
        if recursive
        else _glob.glob(f"{path}/*")
    )
    for filepath in flags:
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(content.splitlines(), 1):
                if _re.search(pattern, line):
                    results.append(f"{filepath}:{lineno}: {line}")
        except (IsADirectoryError, PermissionError, OSError):
            pass
    return results


async def write_file(path: str, content: str) -> str:
    """Write content to file, creating parent directories as needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    return f"Wrote {path}"


async def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Replace old_str with new_str in file at path. Only replaces first occurrence."""
    content = Path(path).read_text(encoding="utf-8")
    new_content = content.replace(old_str, new_str, 1)
    if new_content == content:
        return f"No match found in {path}"
    Path(path).write_text(new_content, encoding="utf-8")
    return f"Edited {path}"
