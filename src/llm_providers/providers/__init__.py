"""Importing this package triggers provider registration as a side effect.

Each module's class body runs @ProviderRegistry.register(...), populating
ProviderRegistry._providers. Order doesn't matter.
"""

from llm_providers.providers import (
    claude,  # noqa: F401
    gemini,  # noqa: F401
    openai,  # noqa: F401
)
