"""ClaudeRuntime — wraps claude_agent_sdk.

Translates the runtime-agnostic AgentOptions into ClaudeAgentOptions
and yields Protocol Messages. No behavior change vs. calling
claude_agent_sdk.query() directly.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
)
from langfuse.decorators import observe

from hsb.runtime.protocol import AgentOptions, Message, RuntimeName


class ClaudeRuntime:
    name: RuntimeName = "claude"

    @observe(as_type="generation")
    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        sdk_options = self._translate(options)
        async for sdk_msg in claude_agent_sdk.query(prompt=prompt, options=sdk_options):
            yield self._to_message(sdk_msg)

    def client(self, options: AgentOptions) -> Any:
        # WIO port lands separately; raise to make accidental use loud.
        raise NotImplementedError(
            "ClaudeRuntime.client() not yet wired — WIO port pending. "
            "Use claude_agent_sdk.ClaudeSDKClient directly until then."
        )

    @staticmethod
    def _translate(options: AgentOptions) -> ClaudeAgentOptions:
        kwargs: dict[str, Any] = dict(
            system_prompt=options.system_prompt,
            allowed_tools=list(options.allowed_tools),
            permission_mode=options.permission_mode,
            max_turns=options.max_turns,
            model=options.model,
        )
        if options.mcp_servers is not None:
            kwargs["mcp_servers"] = options.mcp_servers
        if options.cwd is not None:
            kwargs["cwd"] = options.cwd
        if options.hooks is not None:
            kwargs["hooks"] = options.hooks
        return ClaudeAgentOptions(**kwargs)

    @staticmethod
    def _to_message(sdk_msg: Any) -> Message:
        if isinstance(sdk_msg, ResultMessage):
            return Message(text="", is_final=True, raw=sdk_msg)
        if isinstance(sdk_msg, AssistantMessage):
            text = "".join(getattr(b, "text", "") for b in (sdk_msg.content or []))
            return Message(text=text, is_final=False, raw=sdk_msg)
        return Message(text="", is_final=False, raw=sdk_msg)
