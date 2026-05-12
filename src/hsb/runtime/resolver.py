"""hsb-side runtime resolver — HSB_RUNTIME_<AGENT> → HsbProviderHandle.

Data-driven dispatch: no if/elif/else chain on provider names. Adding
Gemini support is purely operational (set HSB_RUNTIME_BACKLOG=gemini).
"""

from __future__ import annotations

import os
import warnings

from hsb.runtime.handle import HsbProviderHandle
from hsb.runtime.policy import allowed_auth_kinds
from llm_providers.errors import ProviderNotFoundError
from llm_providers.registry import ProviderRegistry

# Per-agent provider hard-blocks. Adding a new block is a one-line tuple edit;
# no other code needs to change.
_HARD_BLOCKED: dict[str, tuple[str, ...]] = {
    # WIO uses ClaudeSDKClient stateful session; no other provider can host it
    # in Phase A. Even "gemini" is blocked preemptively for clarity once it
    # arrives in Phase B.
    "wio": ("openai", "gemini"),
}


def resolve_runtime(agent_name: str) -> HsbProviderHandle:
    """Read HSB_RUNTIME_<AGENT_NAME>; default 'claude'. Return a handle with
    hsb-side policy applied (G1 allowlist, hard-blocks, G3 backstop)."""
    env_var = f"HSB_RUNTIME_{agent_name.upper()}"
    raw = os.environ.get(env_var, "claude").strip().lower()

    # Deprecation alias: "codex" → "openai" for one release.
    if raw == "codex":
        warnings.warn(
            f"{env_var}=codex is deprecated; use =openai (Codex CLI OAuth is "
            "selected automatically when ~/.codex/auth.json is present).",
            DeprecationWarning,
            stacklevel=2,
        )
        raw = "openai"

    blocked = _HARD_BLOCKED.get(agent_name.lower(), ())
    if raw in blocked:
        raise ValueError(
            f"{env_var}={raw!r} is hard-blocked for agent {agent_name!r}. "
            f"Blocked providers: {blocked}. See AGENT-CONTRACTS.md."
        )

    try:
        provider = ProviderRegistry.build_auto(
            raw,
            accepted_kinds=allowed_auth_kinds(agent_name),
        )
    except ProviderNotFoundError as e:
        raise ValueError(
            f"{env_var}={raw!r}: provider {raw!r} is not registered. "
            f"Registered providers: {ProviderRegistry.names()}."
        ) from e

    return HsbProviderHandle(provider=provider, agent_name=agent_name)
