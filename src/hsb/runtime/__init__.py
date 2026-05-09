"""hsb.runtime — runtime-agnostic adapter layer.

Two implementations: ClaudeRuntime (claude_agent_sdk) and CodexRuntime
(openai_codex_sdk). Selection is per-agent via environment variable
HSB_RUNTIME_<AGENT_NAME>. See docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md.
"""
from hsb.runtime.protocol import AgentOptions, Message, Runtime, StatefulClient

__all__ = ["AgentOptions", "Message", "Runtime", "StatefulClient"]
