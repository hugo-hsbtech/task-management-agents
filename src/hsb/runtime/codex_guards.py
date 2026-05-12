"""Deprecation shim — see :mod:`llm_providers.providers._codex_config`.

Re-exports the codex CLI verification helpers from the library. A thin
local wrapper around :func:`assert_codex_oauth_only` is preserved so the
historical "G1-Codex violation" error-message prefix continues to match
existing call-site expectations.

Prefer importing directly from :mod:`llm_providers.providers._codex_config`
for new code.
"""

from __future__ import annotations

from pathlib import (
    Path,  # noqa: TC003  (used as runtime type annotation in legacy callers)
)
from typing import Any

from llm_providers.providers._codex_config import (
    _resolve_codex_home,
    verify_codex_mcp,
)
from llm_providers.providers._codex_config import (
    assert_codex_oauth_only as _lib_assert_codex_oauth_only,
)


def assert_codex_oauth_only(codex_home: Path | None = None) -> dict[str, Any]:
    """Legacy wrapper around the library helper.

    Preserves the historical ``G1-Codex violation`` and
    ``~/.codex/config.toml`` wording in the raised ``RuntimeError`` so
    existing tests and operator-facing error strings keep matching.
    """
    home = _resolve_codex_home(codex_home)
    config_path = home / "config.toml"
    auth_path = home / "auth.json"

    if not config_path.exists():
        raise RuntimeError(
            "G1-Codex violation: ~/.codex/config.toml not found. "
            'Codex CLI must be configured with forced_login_method = "chatgpt". '
            "See GET-STARTED.md Step 1.5."
        )

    # Delegate the rest to the library — which performs the same parse +
    # checks. We catch its RuntimeError to re-raise with the legacy
    # ``G1-Codex violation:`` prefix expected by existing call sites.
    try:
        return _lib_assert_codex_oauth_only(codex_home=codex_home)
    except RuntimeError as e:
        msg = str(e)
        if "forced_login_method" in msg:
            raise RuntimeError(
                f'G1-Codex violation: forced_login_method must be "chatgpt" '
                f"in {config_path} (got from {config_path!s}). "
                "OAuth-only enforcement: API-key auth disallowed. "
                "See GET-STARTED.md Step 1.5."
            ) from e
        if "not authenticated" in msg or auth_path.name in msg:
            raise RuntimeError(
                f"Codex not authenticated: {auth_path} missing. "
                "Run: codex login --device-auth"
            ) from e
        raise


__all__ = [
    "_resolve_codex_home",
    "assert_codex_oauth_only",
    "verify_codex_mcp",
]
