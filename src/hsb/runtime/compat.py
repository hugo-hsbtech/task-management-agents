"""Deprecation shims for the legacy hsb.runtime.{claude,codex} surface.

The library at ``llm_providers`` is now the canonical home for vendor SDK
integration. These shims keep older imports working — primarily
``from hsb.runtime.claude import ClaudeRuntime`` and
``from hsb.runtime.codex import CodexRuntime`` — but emit a
``DeprecationWarning`` on construction so callers know to migrate to
``ProviderRegistry.build_auto(...)``.

Implementation notes:
  * The class bodies stay close to the legacy implementation rather than
    delegating to the library provider, because the legacy tests patch
    module-level attributes on ``hsb.runtime.claude`` /
    ``hsb.runtime.codex`` (``claude_agent_sdk.query``, ``Codex``,
    ``_PERMISSION_MAP``). Routing through library provider instances
    would break that patching surface and force every existing test to
    be rewritten before delete.
  * SDK symbols that tests patch are resolved lazily from the legacy
    modules (``hsb.runtime.claude`` and ``hsb.runtime.codex``) at call
    time, so ``mock.patch("hsb.runtime.codex.Codex", ...)`` continues to
    take effect even though the canonical body lives here.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from hsb.runtime.protocol import AgentOptions, Message, RuntimeName

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


_DEPRECATION_MSG = (
    "{cls} is deprecated; use "
    "llm_providers.ProviderRegistry.build_auto({provider!r}, "
    "accepted_kinds={{'oauth2_cli_token', 'api_key'}}) instead. "
    "This shim will be removed in a future release."
)


# ---------------------------------------------------------------------------
# ClaudeRuntime shim
# ---------------------------------------------------------------------------


class ClaudeRuntime:
    """Legacy adapter around claude_agent_sdk.

    Preserved for backward compatibility. Prefer
    ``ProviderRegistry.build_auto("claude", ...)`` from the
    ``llm_providers`` library.
    """

    name: ClassVar[RuntimeName] = "claude"

    def __init__(self) -> None:
        warnings.warn(
            _DEPRECATION_MSG.format(
                cls="hsb.runtime.claude.ClaudeRuntime", provider="claude"
            ),
            DeprecationWarning,
            stacklevel=2,
        )

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        # Lazy import keeps ``hsb.runtime.claude.claude_agent_sdk.query``
        # patchable from existing tests.
        from hsb.runtime import claude as _claude_mod

        sdk_options = self._translate(options)
        async for sdk_msg in _claude_mod.claude_agent_sdk.query(
            prompt=prompt, options=sdk_options
        ):
            yield self._to_message(sdk_msg)

    def client(self, options: AgentOptions) -> Any:
        # WIO port lands separately; raise to make accidental use loud.
        raise NotImplementedError(
            "ClaudeRuntime.client() not yet wired — WIO port pending. "
            "Use claude_agent_sdk.ClaudeSDKClient directly until then."
        )

    @staticmethod
    def _translate(options: AgentOptions) -> Any:
        from hsb.runtime import claude as _claude_mod

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
        return _claude_mod.ClaudeAgentOptions(**kwargs)

    @staticmethod
    def _to_message(sdk_msg: Any) -> Message:
        from hsb.runtime import claude as _claude_mod

        if isinstance(sdk_msg, _claude_mod.ResultMessage):
            return Message(text="", is_final=True, raw=sdk_msg)
        if isinstance(sdk_msg, _claude_mod.AssistantMessage):
            text = "".join(getattr(b, "text", "") for b in (sdk_msg.content or []))
            return Message(text=text, is_final=False, raw=sdk_msg)
        return Message(text="", is_final=False, raw=sdk_msg)


# ---------------------------------------------------------------------------
# CodexRuntime shim
# ---------------------------------------------------------------------------


class CodexRuntime:
    """Legacy adapter around openai_codex_sdk.Codex.

    Preserved for backward compatibility. Prefer
    ``ProviderRegistry.build_auto("openai", ...)`` from the
    ``llm_providers`` library — OAuth-via-Codex-CLI is selected
    automatically when ``~/.codex/auth.json`` is present.
    """

    name: ClassVar[RuntimeName] = "codex"

    def __init__(self, codex_home: Path | None = None) -> None:
        warnings.warn(
            _DEPRECATION_MSG.format(
                cls="hsb.runtime.codex.CodexRuntime", provider="openai"
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        from hsb.runtime.codex_guards import assert_codex_oauth_only

        self._codex_home = codex_home
        self._cached_config = assert_codex_oauth_only(codex_home=codex_home)

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        # Lazy imports so ``hsb.runtime.codex.Codex`` and
        # ``hsb.runtime.codex._PERMISSION_MAP`` remain patchable for
        # existing tests.
        from hsb.runtime import codex as _codex_mod
        from hsb.runtime.codex_guards import verify_codex_mcp

        if options.hooks is not None:
            raise NotImplementedError(
                "Codex translation: hooks=... not supported (Claude HookMatcher API "
                "has no Codex equivalent). Flipping this agent to Codex disables "
                "hook-based guards."
            )
        if options.mcp_servers:
            verify_codex_mcp(self._cached_config, options.mcp_servers.keys())

        approval_policy = _codex_mod._PERMISSION_MAP.get(options.permission_mode)
        if approval_policy is None:
            raise NotImplementedError(
                f"Codex translation: permission_mode={options.permission_mode!r} "
                "has no mapping."
            )

        full_text = f"<system>{options.system_prompt}</system>\n\n{prompt}"

        thread_options = _codex_mod.ThreadOptions(
            model=options.model,
            # str → Literal narrowed by _PERMISSION_MAP
            approvalPolicy=approval_policy,  # type: ignore[arg-type]
            workingDirectory=options.cwd,
        )
        turn_options = _codex_mod.TurnOptions(
            outputSchema=options.output_schema,
        )

        codex_opts = _codex_mod._build_codex_options()
        codex = (
            _codex_mod.Codex(codex_opts)
            if codex_opts is not None
            else _codex_mod.Codex()
        )
        thread = codex.start_thread(thread_options)
        # Legacy single-TextInput shape; SDK accepts both forms at runtime.
        streamed = await thread.run_streamed(
            _codex_mod.TextInput(type="text", text=full_text),  # type: ignore[arg-type]
            turn_options,
        )

        turns_seen = 0
        final_text_buffer: list[str] = []

        async for evt in streamed.events:
            # Count turn-terminating events (success or failure), not raw
            # stream events. A single agent turn emits many item-level events
            # plus exactly one of {TurnCompletedEvent, TurnFailedEvent}.
            # Counting either ensures the budget is consumed even by a
            # pathological retry loop that only ever fails turns.
            if isinstance(
                evt, _codex_mod.TurnCompletedEvent | _codex_mod.TurnFailedEvent
            ):
                turns_seen += 1
                if turns_seen > options.max_turns:
                    raise RuntimeError(
                        f"Codex exceeded max_turns={options.max_turns}; aborting."
                    )

            evt_text = _codex_mod._extract_event_text(evt)
            if evt_text:
                final_text_buffer.append(evt_text)

            yield Message(
                text=evt_text,
                is_final=False,
                raw=evt,
            )

        # After the stream ends, emit a synthetic final Message carrying the
        # accumulated text. This is the runtime-agnostic completion sentinel
        # that runtime-aware agents (e.g. Backlog) consume via message.is_final.
        yield Message(
            text="".join(final_text_buffer),
            is_final=True,
            raw=None,
        )

    def client(self, options: AgentOptions) -> Any:
        raise NotImplementedError(
            "CodexRuntime.client() not yet wired — WIO port pending. "
            "Use openai_codex_sdk.Thread directly until then."
        )


__all__ = ["ClaudeRuntime", "CodexRuntime"]
