"""Codex CLI configuration.

Read by `runtime/codex.py` (CODEX_PATH_OVERRIDE) and `runtime/codex_guards.py` (CODEX_HOME).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CodexSettings(BaseSettings):
    """CODEX_HOME (Codex auth dir) and CODEX_PATH_OVERRIDE (explicit codex binary path)."""

    model_config = SettingsConfigDict(env_prefix="CODEX_")

    home: Path | None = None
    path_override: Path | None = None
