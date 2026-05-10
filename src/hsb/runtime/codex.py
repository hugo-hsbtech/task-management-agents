"""CodexRuntime — wraps openai_codex_sdk.Codex.

Translation table (Backlog-scoped surface):
  system_prompt   → prepended to prompt as <system>...</system> block in TextInput
  model           → ThreadOptions(model=...)
  mcp_servers     → verified against ~/.codex/config.toml; not configured here
  permission_mode → ThreadOptions(approvalPolicy=...)
                    "bypassPermissions"/"acceptEdits" → "never"
                    "default"/"plan"                  → "on-request"
  cwd             → ThreadOptions(workingDirectory=...)
  output_schema   → TurnOptions(outputSchema=...)
  max_turns       → counted via Turn{Completed,Failed}Event boundaries; aborts once exceeded
  hooks           → NotImplementedError (Claude-only HookMatcher API)
  allowed_tools   → currently passthrough; tighter mapping deferred until needed
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from openai_codex_sdk import (
    Codex,
    TextInput,
    ThreadOptions,
    TurnCompletedEvent,
    TurnFailedEvent,
    TurnOptions,
)
from langfuse import observe
from openai_codex_sdk.types import CodexOptions

from hsb.runtime.codex_guards import assert_codex_oauth_only, verify_codex_mcp
from hsb.runtime.protocol import (
    AgentOptions,
    Message,
    PermissionMode,
    RuntimeName,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


def _extract_event_text(evt: Any) -> str:
    """Pull the text payload from a Codex ThreadEvent.

    Real Codex events vary: AgentMessageItem has a .text on its content
    blocks; ItemCompletedEvent wraps an item; SimpleNamespace fakes used
    in tests just have .text. Return "" if nothing readable.
    """
    direct = getattr(evt, "text", None)
    if isinstance(direct, str) and direct:
        return direct
    item = getattr(evt, "item", None)
    if item is not None:
        item_text = getattr(item, "text", None)
        if isinstance(item_text, str) and item_text:
            return item_text
    return ""


_PERMISSION_MAP: dict[PermissionMode, str] = {
    "default": "on-request",
    "acceptEdits": "never",
    "plan": "on-request",
    "bypassPermissions": "never",
}


def _build_codex_options() -> CodexOptions | None:
    """Honor CODEX_PATH_OVERRIDE so operators can reuse a globally-installed
    `codex` binary (npm i -g @openai/codex) without populating the SDK's
    vendor dir. Returns None when no override is set, letting the SDK fall
    back to find_codex_path().
    """
    override = os.environ.get("CODEX_PATH_OVERRIDE")
    if override:
        return CodexOptions(codex_path_override=override)
    return None


class CodexRuntime:
    name: RuntimeName = "codex"

    def __init__(self, codex_home: Path | None = None) -> None:
        self._codex_home = codex_home
        self._cached_config = assert_codex_oauth_only(codex_home=codex_home)

    @observe(as_type="generation")
    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        # Hooks are now handled by the UniversalOrchestrator (Phase 2/3).
        # We ignore them here to avoid crashing, as they are now agnostic.

        if options.mcp_servers:
            verify_codex_mcp(self._cached_config, options.mcp_servers.keys())

        approval_policy = _PERMISSION_MAP.get(options.permission_mode)
        if approval_policy is None:
            raise NotImplementedError(
                f"Codex translation: permission_mode={options.permission_mode!r} "
                "has no mapping."
            )

        full_text = f"<system>{options.system_prompt}</system>\n\n{prompt}"

        thread_options = ThreadOptions(
            model=options.model,
            approvalPolicy=approval_policy,
            workingDirectory=options.cwd,
        )
        turn_options = TurnOptions(
            outputSchema=options.output_schema,
        )

        codex_opts = _build_codex_options()
        codex = Codex(codex_opts) if codex_opts is not None else Codex()
        thread = codex.start_thread(thread_options)
        streamed = await thread.run_streamed(
            TextInput(type="text", text=full_text),
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
            if isinstance(evt, TurnCompletedEvent | TurnFailedEvent):
                turns_seen += 1
                if turns_seen > options.max_turns:
                    raise RuntimeError(
                        f"Codex exceeded max_turns={options.max_turns}; aborting."
                    )

            # Extract text from the event using the SDK's typed attributes
            # where present, falling back to a generic .text attr for fakes.
            evt_text = _extract_event_text(evt)
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
