"""Linear MCP fallback authentication.

Phase 1 prefers OAuth via mcp-remote (D-01); the API-key path is the
headless/CI fallback. Env var: LINEAR_API_KEY.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from settings.provider import ProviderSettings


class LinearSettings(BaseSettings):
    """Linear MCP configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LINEAR_",
        env_nested_delimiter="_",
    )

    provider: ProviderSettings = ProviderSettings()
    api_key: SecretStr | None = None
    mcp_url: str = (
        "https://mcp.linear.app/mcp"  # LINEAR_MCP_URL to override (e.g. self-hosted)
    )
    audit_log_path: str = ".linear/audit.log"  # appended by linear_audit_hook on every mcp__linear__* call
    compaction_archive_dir: str = ".linear/compaction"  # transcript copy destination before Claude context compaction
