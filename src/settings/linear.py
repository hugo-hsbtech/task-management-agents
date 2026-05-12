"""Linear MCP fallback authentication.

Phase 1 prefers OAuth via mcp-remote (D-01); the API-key path is the
headless/CI fallback. Env var: LINEAR_API_KEY.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LinearSettings(BaseSettings):
    """Linear MCP configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LINEAR_",
        env_nested_delimiter="_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    api_key: SecretStr | None = None
