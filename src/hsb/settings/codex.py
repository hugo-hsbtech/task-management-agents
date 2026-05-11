"""Codex CLI configuration.

Read by `runtime/codex.py` (CODEX_PATH_OVERRIDE) and
`runtime/codex_guards.py` (CODEX_HOME).

Defaults target the project's primary deployment surface: a Docker
container running as root. Local developers running on the host
override via environment variables.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CodexSettings(BaseSettings):
    """CODEX_HOME (Codex auth dir) and CODEX_PATH_OVERRIDE (explicit codex binary path)."""

    model_config = SettingsConfigDict(env_prefix="CODEX_")

    # Default matches the container's root-user home — what `codex login`
    # writes to inside the project's Docker image. Override on host
    # development with CODEX_HOME=$HOME/.codex.
    home: Path = Path("/root/.codex")

    # No default — when unset, `runtime/codex.py` uses the PATH lookup
    # for the `codex` binary. Override only if Codex lives outside PATH.
    path_override: Path | None = None
