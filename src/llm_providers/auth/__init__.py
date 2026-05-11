"""Auth strategies. Importing this package triggers strategy registration."""

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential

__all__ = ["ApiKey", "AuthStrategy", "Credential"]
