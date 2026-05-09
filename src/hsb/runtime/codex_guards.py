"""Codex-side analogues of the G1 guards.

Two helpers:
- assert_codex_oauth_only(codex_home=None): one-shot init-time check.
  Verifies ~/.codex/config.toml has `forced_login_method = "chatgpt"` and
  ~/.codex/auth.json exists. Returns the parsed config dict so the caller
  can cache it instead of re-reading per call.
- verify_codex_mcp(parsed_config, requested_servers): per-call check.
  For each requested MCP server name, asserts a [mcp_servers.<name>] block
  is present in the cached parsed config.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Iterable


def _resolve_codex_home(codex_home: Path | None = None) -> Path:
    if codex_home is not None:
        return codex_home
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codex"


def assert_codex_oauth_only(codex_home: Path | None = None) -> dict[str, Any]:
    """Init-time check. Returns the parsed config.toml dict."""
    home = _resolve_codex_home(codex_home)
    config_path = home / "config.toml"
    auth_path = home / "auth.json"

    if not config_path.exists():
        raise RuntimeError(
            "G1-Codex violation: ~/.codex/config.toml not found. "
            "Codex CLI must be configured with forced_login_method = \"chatgpt\". "
            "See GET-STARTED.md Step 1.5."
        )
    parsed = tomllib.loads(config_path.read_text())

    if parsed.get("forced_login_method") != "chatgpt":
        raise RuntimeError(
            f"G1-Codex violation: forced_login_method must be \"chatgpt\" "
            f"in {config_path} (got {parsed.get('forced_login_method')!r}). "
            "OAuth-only enforcement: API-key auth disallowed. "
            "See GET-STARTED.md Step 1.5."
        )

    if not auth_path.exists():
        raise RuntimeError(
            f"Codex not authenticated: {auth_path} missing. "
            "Run: codex login --device-auth"
        )

    return parsed


def verify_codex_mcp(parsed_config: dict, requested_servers: Iterable[str]) -> None:
    """Per-call check. Cheap dict lookup against cached parsed config."""
    available = (parsed_config.get("mcp_servers") or {}).keys()
    missing = [s for s in requested_servers if s not in available]
    if missing:
        raise RuntimeError(
            f"Codex MCP missing: [mcp_servers.{', mcp_servers.'.join(missing)}] "
            f"block(s) not found in ~/.codex/config.toml. "
            "Add the block(s) (see GET-STARTED.md Step 1.5)."
        )
