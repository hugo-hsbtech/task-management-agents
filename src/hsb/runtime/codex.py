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
  max_turns       → tracked locally; aborts iteration once exceeded
  hooks           → NotImplementedError (Claude-only HookMatcher API)
  allowed_tools   → currently passthrough; tighter mapping deferred until needed
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncIterator

from openai_codex_sdk import (
    Codex,
    TextInput,
    ThreadOptions,
    TurnOptions,
)
from openai_codex_sdk.types import CodexOptions

from hsb.runtime.codex_guards import assert_codex_oauth_only, verify_codex_mcp
from hsb.runtime.protocol import (
    AgentOptions,
    Message,
    PermissionMode,
    RuntimeName,
)


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

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        if options.hooks is not None:
            raise NotImplementedError(
                "Codex translation: hooks=... not supported (Claude HookMatcher API "
                "has no Codex equivalent). Flipping this agent to Codex disables "
                "hook-based guards."
            )
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
        async for evt in streamed.events:
            turns_seen += 1
            if turns_seen > options.max_turns:
                raise RuntimeError(
                    f"Codex exceeded max_turns={options.max_turns}; aborting."
                )
            yield Message(
                text=getattr(evt, "text", "") or "",
                is_final=getattr(evt, "is_final", False),
                raw=evt,
            )

    def client(self, options: AgentOptions) -> Any:
        raise NotImplementedError(
            "CodexRuntime.client() not yet wired — WIO port pending. "
            "Use openai_codex_sdk.Thread directly until then."
        )
