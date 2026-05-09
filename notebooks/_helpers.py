"""Shared helpers for the manual inspection notebooks.

Keep this thin — anything more than imports + tiny utility shims belongs in
src/hsb/. The notebooks should be readable end-to-end without chasing helpers.

Runtime-agnostic since the alt-runtime work landed (see
docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md). Each
agent picks its runtime via HSB_RUNTIME_<AGENT_NAME>; the helpers here let a
notebook show what's selected without committing to a specific runtime.
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

# Agents that run through the Runtime Protocol today. Used by runtime_summary()
# to render a one-line table of "agent -> runtime" so a notebook makes the
# operator's HSB_RUNTIME_* environment legible at a glance.
RUNTIME_AGENTS: tuple[str, ...] = (
    "backlog",
    "builder",
    "git",
    "qa",
    "uat",
    "linear",
    "risk",
    "intelligence",
    "wio",
)


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
    """G1 sanity check — refuse to proceed if a metered API key is set.

    Mirrors :func:`hsb.agents._sdk_options.assert_oauth2_only` which forbids
    both ANTHROPIC_API_KEY (Claude) and OPENAI_API_KEY (Codex). Run this
    before any cell that constructs SDK options. Function-time, NOT
    module-import-time, so notebook startup never crashes when an unrelated
    process leaves a key in the env.
    """
    forbidden = [v for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )


def selected_runtime(agent_name: str) -> str:
    """Return the runtime selected for ``agent_name`` per HSB_RUNTIME_<NAME>.

    Mirrors the read in :func:`hsb.agents._sdk_options.resolve_runtime` but
    does NOT instantiate the runtime — the notebook may want to render the
    selection without paying the cost of constructing ``CodexRuntime`` (which
    asserts ~/.codex config on init).

    A missing or empty value defaults to ``"claude"`` (the resolver default);
    any other value is returned as-is so the notebook display matches what
    ``resolve_runtime`` would see — including the invalid values it would
    reject. Callers should NOT treat the return as pre-validated.
    """
    env_var = f"HSB_RUNTIME_{agent_name.upper()}"
    raw = os.environ.get(env_var)
    if raw is None:
        return "claude"
    value = raw.strip().lower()
    return value or "claude"


def runtime_summary() -> str:
    """One-line-per-agent rendering of HSB_RUNTIME_* selection.

    Use at the top of any notebook that touches an agent through the runtime
    protocol — makes it obvious whether the cells below will exercise Claude
    or Codex.
    """
    rows = [f"  {a:>12s}  ->  {selected_runtime(a)}" for a in RUNTIME_AGENTS]
    return "\n".join(rows)


def codex_available(codex_home: Path | None = None) -> tuple[bool, str]:
    """Cheap reachability probe for the Codex runtime — does NOT call OpenAI.

    Returns ``(ok, reason)``. ``ok=True`` only when ~/.codex/config.toml has
    ``forced_login_method = "chatgpt"`` AND ~/.codex/auth.json exists. Mirrors
    :func:`hsb.runtime.codex_guards.assert_codex_oauth_only` without raising
    so notebook cells can render a polite 'codex unavailable' instead of a
    traceback.
    """
    home = codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    config = home / "config.toml"
    auth = home / "auth.json"
    if not config.exists():
        return False, f"missing {config}"
    try:
        parsed = tomllib.loads(config.read_text())
    except tomllib.TOMLDecodeError as e:
        return False, f"invalid TOML in {config}: {e}"
    if parsed.get("forced_login_method") != "chatgpt":
        return False, (
            f'forced_login_method must be "chatgpt" in {config} '
            f"(got {parsed.get('forced_login_method')!r})"
        )
    if not auth.exists():
        return (
            False,
            f"not authenticated: {auth} missing — run `codex login --device-auth`",
        )
    return True, f"OK ({home})"
