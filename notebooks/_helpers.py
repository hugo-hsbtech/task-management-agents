"""Shared helpers for the manual inspection notebooks.

Keep this thin — anything more than imports + tiny utility shims belongs in
src/hsb/. The notebooks should be readable end-to-end without chasing helpers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    """Walk upward from this file until we find pyproject.toml.

    The notebooks may be opened with `jupyter lab notebooks/` or from any cwd,
    so don't rely on cwd or __file__ heuristics that assume a specific layout.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError("Could not locate repo root (no pyproject.toml found upwards)")


def ensure_src_on_path() -> Path:
    """Insert <repo_root>/src on sys.path so notebooks can `import hsb` even
    without an editable install."""
    root = repo_root()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return root


def live_mode() -> bool:
    """True iff the notebook is allowed to make real SDK / Linear MCP calls.

    Intentionally restrictive default — running a notebook should never burn
    tokens or touch Linear unless the operator explicitly opts in.
    """
    return os.environ.get("HSB_NOTEBOOK_RUN_LIVE", "") == "1"


def gated(reason: str) -> str:
    """Format a uniform 'cell skipped' banner the operator can scan for."""
    return f"[skipped] {reason}  — set HSB_NOTEBOOK_RUN_LIVE=1 to run live"


def assert_g1_safe() -> None:
    """G1 sanity check — refuse to proceed if ANTHROPIC_API_KEY is set.

    Mirrors the function-entry guard in src/hsb/agents/_sdk_options.py. Run
    this before any cell that constructs SDK options. Function-time, NOT
    module-import-time, so notebook startup never crashes.
    """
    if "ANTHROPIC_API_KEY" in os.environ:
        raise RuntimeError(
            "G1 violation: ANTHROPIC_API_KEY is set. HSBTech is OAuth2-only. "
            "Unset it (use CLAUDE_CODE_OAUTH_TOKEN) before running this cell."
        )
