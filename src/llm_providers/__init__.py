"""llm_providers — decoupled multi-provider LLM library.

Public surface is re-exported from this module. Importing this package
also triggers provider and auth-strategy registration as a side effect.
"""

from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)

__all__ = [
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
]
