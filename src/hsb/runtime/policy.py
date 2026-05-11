"""hsb runtime policy — G1 OAuth2-only allowlist + per-agent escape hatch.

The llm_providers library is policy-free; hsb imposes "OAuth2 preferred,
API key only when explicitly allowed per-agent" here.
"""

from __future__ import annotations

import os

_DEFAULT_ALLOWED_AUTH_KINDS: frozenset[str] = frozenset(
    {
        "oauth2_cli_token",
        "oauth2_adc",
        "oauth2_service_account",
    }
)


def allowed_auth_kinds(agent_name: str) -> frozenset[str]:
    """Return the auth-kind allowlist for the given agent.

    Default: OAuth2 strategies only (G1 enforcement).
    Per-agent escape: HSB_AUTH_ALLOW_API_KEY_<AGENT>=1 widens the set to
    include "api_key" for that agent only. Documented in GET-STARTED.md.

    There is intentionally no global toggle — flipping one agent is a
    per-operator decision; flipping all is a project-policy change that
    edits this allowlist directly.
    """
    base = set(_DEFAULT_ALLOWED_AUTH_KINDS)
    if os.environ.get(f"HSB_AUTH_ALLOW_API_KEY_{agent_name.upper()}") == "1":
        base.add("api_key")
    return frozenset(base)
