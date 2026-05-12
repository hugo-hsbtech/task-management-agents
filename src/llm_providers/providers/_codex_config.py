"""Codex CLI configuration parsing — ports hsb.runtime.codex_guards into
the library so OpenAIProvider's Codex backend has no dependency on hsb.

Two helpers:
  - assert_codex_oauth_only(codex_home=None): init-time. Verifies
    ~/.codex/config.toml has `forced_login_method = "chatgpt"` and
    ~/.codex/auth.json exists. Returns the parsed config so the caller
    can cache it.
  - verify_codex_mcp(parsed_config, requested_servers): per-call check.
    For each requested MCP server name, asserts a [mcp_servers.<name>]
    block exists in the parsed config.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable


def _resolve_codex_home(codex_home: Path | None = None) -> Path:
    if codex_home is not None:
        return codex_home
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codex"


def assert_codex_oauth_only(codex_home: Path | None = None) -> dict[str, Any]:
    """Init-time check. Returns the parsed config.toml dict.

    Caller should cache the return value and pass it to verify_codex_mcp on
    each query() call to avoid re-reading the file.
    """
    home = _resolve_codex_home(codex_home)
    config_path = home / "config.toml"
    auth_path = home / "auth.json"

    if not config_path.exists():
        raise RuntimeError(
            f"Codex config.toml not found at {config_path}. "
            'Codex CLI must be configured with forced_login_method = "chatgpt". '
            "See https://platform.openai.com/docs/codex for setup."
        )
    parsed: dict[str, Any] = tomllib.loads(config_path.read_text())

    if parsed.get("forced_login_method") != "chatgpt":
        raise RuntimeError(
            f'Codex forced_login_method must be "chatgpt" in {config_path} '
            f"(got {parsed.get('forced_login_method')!r}). OAuth-only "
            "enforcement: API-key auth disallowed by this strategy."
        )

    if not auth_path.exists():
        raise RuntimeError(
            f"Codex not authenticated: {auth_path} missing. "
            "Run: codex login --device-auth"
        )

    return parsed


def verify_codex_mcp(
    parsed_config: dict[str, Any], requested_servers: Iterable[str]
) -> None:
    """Per-call cheap dict lookup against cached parsed config."""
    available = (parsed_config.get("mcp_servers") or {}).keys()
    missing = [s for s in requested_servers if s not in available]
    if missing:
        raise RuntimeError(
            f"Codex MCP missing: [mcp_servers.{', mcp_servers.'.join(missing)}] "
            f"block(s) not found in Codex config.toml."
        )
