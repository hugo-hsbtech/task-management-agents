"""ClaudeProvider — wraps claude_agent_sdk."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, ClassVar

import claude_agent_sdk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

from libs.logging import get_logger
from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import (
    ClaudeAuthError,
    ClaudeRateLimitError,
    ProviderRuntimeError,
    TranslationError,
)
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy

logger = get_logger(__name__)

# Regex pinned to the canonical Claude CLI rate-limit phrase. Anchored on
# `resets` to avoid matching arbitrary text containing "reset" elsewhere.
_RATE_LIMIT_RESET_RE = re.compile(
    r"resets?\s+(?P<when>[A-Za-z0-9:\s\-+()]+?)(?:[.,]|$)",
    re.IGNORECASE,
)

# Sentinel typed-exception names from claude_agent_sdk that map directly to
# our error hierarchy. Used in preference to fragile substring matching.
_RATE_LIMIT_EXC_NAMES = frozenset({"RateLimitError", "QuotaExceededError"})
_AUTH_EXC_NAMES = frozenset(
    {
        "AuthenticationError",
        "PermissionDeniedError",
        "InvalidTokenError",
    }
)


@ProviderRegistry.register("claude")
class ClaudeProvider(BaseProvider):
    """Native Claude provider using claude_agent_sdk.

    Recognized ProviderOptions.extras["claude"] keys:
      - "hooks": list of HookMatcher instances (Claude-only).

    Supported auth kinds (resolved by
    :func:`llm_providers.auth.factory.resolve_auth`):
      - ``oauth2_cli_token`` from ``CLAUDE_CODE_OAUTH_TOKEN``
      - ``api_key`` from ``ANTHROPIC_API_KEY`` (gated by G1 escape hatch)
    """

    name: ClassVar[str] = "claude"
    capabilities: ClassVar[Capabilities] = Capabilities(
        supports_mcp=True,
        supports_native_tools=True,
        supports_hooks=True,
        supports_stateful_client=True,
        supports_output_schema=True,
        supports_system_prompt_file=True,
        supports_streaming=True,
    )
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (
        OAuth2CliToken,
        ApiKey,
    )

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        self._sdk = claude_agent_sdk
        # Pre-resolve the credential and stash the env-shaped overrides we'll
        # hand to ClaudeAgentOptions(env=...). We never write to os.environ.
        self._sdk_env: dict[str, str] = self._build_sdk_env(self._auth.resolve())

    @staticmethod
    def _build_sdk_env(cred: Any) -> dict[str, str]:
        """Return the per-call env override the SDK expects for this auth kind."""
        if cred.kind == "oauth2_cli_token":
            return {"CLAUDE_CODE_OAUTH_TOKEN": cred.payload["token"]}
        if cred.kind == "api_key":
            return {"ANTHROPIC_API_KEY": cred.payload["api_key"]}
        logger.warning(
            "claude.unknown_credential_kind",
            kind=getattr(cred, "kind", None),
        )
        return {}

    async def query(  # type: ignore[override,misc]
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        sdk_options = self._build_native_options(options)
        try:
            async for sdk_msg in self._sdk.query(prompt=prompt, options=sdk_options):
                yield self._to_message(sdk_msg)
        except Exception as e:
            raise self._classify_exception(e) from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        sdk_options = self._build_native_options(options)
        try:
            sdk_client = self._sdk.ClaudeSDKClient(options=sdk_options)
        except Exception as e:
            logger.error("claude.client_init_failed", error=str(e))
            raise ProviderRuntimeError(provider=self.name, phase="client_init") from e
        return _ClaudeStatefulClient(sdk_client, self._to_message)  # type: ignore[return-value]

    # ---- Error classification ----------------------------------------------

    def _classify_exception(self, exc: Exception) -> Exception:
        """Map an SDK exception to the project's error hierarchy.

        Prefers the SDK's typed exception name; falls back to a narrow set of
        canonical phrases only when the type doesn't tell us enough.
        """
        exc_type_name = type(exc).__name__
        original = str(exc)
        lower = original.lower()

        if exc_type_name in _RATE_LIMIT_EXC_NAMES or "hit your limit" in lower:
            reset_match = _RATE_LIMIT_RESET_RE.search(original)
            reset_time = reset_match.group("when").strip() if reset_match else None
            logger.warning(
                "claude.rate_limit",
                exc_type=exc_type_name,
                reset_time=reset_time,
            )
            return ClaudeRateLimitError(reset_time=reset_time)

        if exc_type_name in _AUTH_EXC_NAMES or "oauth_token_invalid" in lower:
            logger.warning("claude.auth_failed", exc_type=exc_type_name)
            return ClaudeAuthError(reason=original)

        if "error result: success" in lower:
            logger.error(
                "claude.malformed_error_result",
                exc_type=exc_type_name,
                original=original,
            )
            return ProviderRuntimeError(
                provider=self.name,
                phase="query",
                message=(
                    "Claude CLI returned malformed error. "
                    "This often indicates: (1) rate limit reached, "
                    "(2) invalid OAuth token, or (3) Claude CLI not authenticated. "
                    f"Run 'claude config get oauth_token' to verify. Original: {original}"
                ),
            )

        logger.error(
            "claude.query_failed",
            exc_type=exc_type_name,
            original=original,
        )
        return ProviderRuntimeError(
            provider=self.name,
            phase="query",
            message=f"Claude query failed: {original}",
        )

    # ---- Translation hooks ---------------------------------------------------

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            return {"type": "preset", "preset": sp.preset_id}
        raise TranslationError(f"Unknown SystemPrompt subtype: {type(sp).__name__}")

    def _translate_tools(self, policy: ToolPolicy) -> dict[str, Any]:
        return {"allowed_tools": list(policy.allowed)}

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> dict[str, Any]:
        """Translate MCP servers to Claude SDK format.

        Claude SDK only supports STDIO transport. HTTP MCP servers are
        automatically converted to STDIO via mcp-remote proxy.
        """
        out: dict[str, dict[str, Any]] = {}
        for s in servers:
            if s.transport == "http":
                if s.url is None:
                    raise TranslationError(
                        f"McpServerSpec {s.name!r}: transport='http' requires url=..."
                    )
                entry: dict[str, Any] = {
                    "transport": "stdio",
                    "command": f"npx -y mcp-remote {s.url}",
                }
                if s.env:
                    entry["env"] = dict(s.env)
                out[s.name] = entry
            elif s.transport == "stdio":
                if not s.command:
                    raise TranslationError(
                        f"McpServerSpec {s.name!r}: transport='stdio' requires "
                        "a non-empty command=(...)."
                    )
                entry = {
                    "transport": "stdio",
                    "command": s.command[0],
                    "args": list(s.command[1:]),
                }
                if s.env:
                    entry["env"] = dict(s.env)
                out[s.name] = entry
            else:
                raise TranslationError(
                    f"McpServerSpec {s.name!r}: unsupported transport={s.transport!r}"
                )
        return out

    # ---- Helpers -------------------------------------------------------------

    def _build_native_options(self, options: ProviderOptions) -> Any:
        sp = self._translate_system_prompt(options.system_prompt)
        tools = self._translate_tools(options.tool_policy)
        mcp = self._translate_mcp(options.mcp_servers) if options.mcp_servers else None
        kwargs: dict[str, Any] = {
            "system_prompt": sp,
            "allowed_tools": tools["allowed_tools"],
            "permission_mode": options.permission_mode,
            "max_turns": options.max_turns,
            "model": options.model,
            # Pass the credential to the SDK explicitly. The SDK forwards this
            # to its subprocess as env overlay — no process-wide mutation.
            "env": dict(self._sdk_env),
        }
        if mcp is not None:
            kwargs["mcp_servers"] = mcp
        if options.cwd is not None:
            kwargs["cwd"] = options.cwd
        if options.output_schema is not None:
            kwargs["output_format"] = {
                "type": "json_schema",
                "schema": options.output_schema,
            }
        extras = options.extras.get(self.name, {}) if options.extras else {}
        if "hooks" in extras:
            kwargs["hooks"] = extras["hooks"]
        return self._sdk.ClaudeAgentOptions(**kwargs)

    def _to_message(self, sdk_msg: Any) -> Message:
        if isinstance(sdk_msg, self._sdk.ResultMessage):
            subtype = getattr(sdk_msg, "subtype", None)
            if subtype not in (None, "success"):
                raise RuntimeError(f"Claude agent failed: {subtype}")
            structured_output = getattr(sdk_msg, "structured_output", None)
            if structured_output is not None:
                text = json.dumps(structured_output)
            else:
                text = getattr(sdk_msg, "result", None) or ""
            return Message(text=text, is_final=True, raw=sdk_msg)
        if isinstance(sdk_msg, self._sdk.AssistantMessage):
            text = "".join(getattr(b, "text", "") for b in (sdk_msg.content or []))
            return Message(text=text, is_final=False, raw=sdk_msg)
        return Message(text="", is_final=False, raw=sdk_msg)


class _ClaudeStatefulClient:
    """Adapter from claude_agent_sdk.ClaudeSDKClient to StatefulClient Protocol."""

    def __init__(
        self,
        sdk_client: Any,
        to_message: Callable[[Any], Message],
    ) -> None:
        self._inner = sdk_client
        self._to_message = to_message

    async def __aenter__(self) -> _ClaudeStatefulClient:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._inner.__aexit__(*exc)

    async def query(self, prompt: str) -> AsyncIterator[Message]:
        try:
            async for sdk_msg in self._inner.query(prompt):
                yield self._to_message(sdk_msg)
        except ProviderRuntimeError:
            raise
        except Exception as e:
            logger.error("claude.client_query_failed", error=str(e))
            raise ProviderRuntimeError(provider="claude", phase="client_query") from e
