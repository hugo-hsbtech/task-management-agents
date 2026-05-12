"""Tools for provider-agnostic agent integration.

Each module defines ToolSpec declarations that work across Codex, Claude, and Gemini
via the llm_providers translation layer.
"""

from __future__ import annotations

from tools.linear import LinearTools

__all__ = ["LinearTools"]
