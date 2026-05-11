"""hsb.runtime.policy — G1 OAuth2-only allowlist + per-agent escape hatch."""

from hsb.runtime.policy import allowed_auth_kinds


def test_default_excludes_api_key(monkeypatch):
    for v in ("HSB_AUTH_ALLOW_API_KEY_BACKLOG",):
        monkeypatch.delenv(v, raising=False)
    kinds = set(allowed_auth_kinds("backlog"))
    assert "api_key" not in kinds
    assert "oauth2_cli_token" in kinds


def test_per_agent_escape_hatch_includes_api_key(monkeypatch):
    monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", "1")
    kinds = set(allowed_auth_kinds("backlog"))
    assert "api_key" in kinds


def test_per_agent_escape_hatch_is_per_agent(monkeypatch):
    monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", "1")
    monkeypatch.delenv("HSB_AUTH_ALLOW_API_KEY_UAT", raising=False)
    assert "api_key" in set(allowed_auth_kinds("backlog"))
    assert "api_key" not in set(allowed_auth_kinds("uat"))


def test_returns_frozenset():
    kinds = allowed_auth_kinds("backlog")
    assert isinstance(kinds, frozenset)
