"""Auth strategies.

Importing this package eagerly imports each strategy module, which in turn
applies the ``@AuthRegistry.register(...)`` decorator at class-definition
time. The registry is therefore populated as a side effect of this import.
"""

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken

__all__ = ["ApiKey", "AuthStrategy", "Credential", "OAuth2CliToken"]
