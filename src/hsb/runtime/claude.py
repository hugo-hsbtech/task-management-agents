"""Deprecation shim — see :mod:`hsb.runtime.compat`.

The canonical body lives in :mod:`hsb.runtime.compat`. SDK symbols are
re-exported here so existing call sites (and ``mock.patch`` targets in
the test suite) keep resolving to module-level names on
``hsb.runtime.claude``.

Prefer ``llm_providers.ProviderRegistry.build_auto("claude", ...)`` for
new code.
"""

from __future__ import annotations

# Module-level re-exports of the SDK symbols the legacy runtime touched.
# Tests patch ``hsb.runtime.claude.claude_agent_sdk.query`` — keeping the
# module imported here means the patch target resolves correctly.
import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
)

from hsb.runtime.compat import ClaudeRuntime

__all__ = [
    "AssistantMessage",
    "ClaudeAgentOptions",
    "ClaudeRuntime",
    "ResultMessage",
    "claude_agent_sdk",
]
