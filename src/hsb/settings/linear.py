"""Linear MCP fallback authentication.

Phase 1 prefers OAuth via mcp-remote (D-01); the API-key path is the
headless/CI fallback. Env var: LINEAR_API_KEY.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LinearSettings(BaseSettings):
    """Optional Linear API key for non-OAuth Linear MCP authentication."""

    model_config = SettingsConfigDict(env_prefix="LINEAR_")

    api_key: SecretStr | None = None
