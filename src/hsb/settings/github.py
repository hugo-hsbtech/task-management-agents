"""Optional GitHub PAT for non-interactive `gh auth login --with-token`.

If absent, operator uses the interactive device flow. Env var: GITHUB_TOKEN.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """Optional Personal Access Token for non-interactive `gh auth login`."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_")

    token: SecretStr | None = None
