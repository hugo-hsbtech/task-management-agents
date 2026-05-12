"""hsb.runtime — runtime-agnostic adapter layer.

The canonical home for multi-provider work is the :mod:`llm_providers`
library. This package re-exports the legacy ``AgentOptions`` /
``Message`` / ``Runtime`` surface alongside the library types so callers
can migrate incrementally. See
``docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md``.
"""

from hsb.runtime.protocol import (
    AgentOptions,
    Message,
    PermissionMode,
    Runtime,
    RuntimeName,
    StatefulClient,
)
from llm_providers.protocol import (
    Capabilities,
    ProviderOptions,
)

__all__ = [
    "AgentOptions",
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
    "Runtime",
    "RuntimeName",
    "StatefulClient",
]
