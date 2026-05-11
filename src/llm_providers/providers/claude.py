"""ClaudeProvider — wraps claude_agent_sdk."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import ProviderRuntimeError, TranslationError
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


class _ClaudeOAuth2CliToken(OAuth2CliToken):
    """OAuth2 token pre-wired to CLAUDE_CODE_OAUTH_TOKEN for auto-detection."""

    @classmethod
    def default(cls) -> _ClaudeOAuth2CliToken:
        return cls(env_var="CLAUDE_CODE_OAUTH_TOKEN")


class _ClaudeApiKey(ApiKey):
    """ApiKey pre-wired to ANTHROPIC_API_KEY for auto-detection."""

    @classmethod
    def default(cls) -> _ClaudeApiKey:
        return cls(env_var="ANTHROPIC_API_KEY")


@ProviderRegistry.register("claude")
class ClaudeProvider(BaseProvider):
    """Native Claude provider using claude_agent_sdk.

    Recognized ProviderOptions.extras["claude"] keys:
      - "hooks": list of HookMatcher instances (Claude-only).
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
    # _ClaudeOAuth2CliToken / _ClaudeApiKey appear first so auto_resolve_auth
    # walks their pre-wired default() (which knows the canonical env vars).
    # OAuth2CliToken / ApiKey remain in the tuple so callers constructing
    # them directly (e.g. tests, explicit wiring) still satisfy
    # _validate_auth's isinstance check.
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (
        _ClaudeOAuth2CliToken,
        _ClaudeApiKey,
        OAuth2CliToken,
        ApiKey,
    )

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        import claude_agent_sdk

        self._sdk = claude_agent_sdk
        self._apply_credential()

    def _apply_credential(self) -> None:
        """Inject the resolved credential into the env var the SDK reads."""
        import os

        cred = self._auth.resolve()
        if cred.kind == "oauth2_cli_token":
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = cred.payload["token"]
        elif cred.kind == "api_key":
            os.environ["ANTHROPIC_API_KEY"] = cred.payload["api_key"]

    async def query(  # type: ignore[override,misc]
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        sdk_options = self._build_native_options(options)
        try:
            async for sdk_msg in self._sdk.query(prompt=prompt, options=sdk_options):
                yield self._to_message(sdk_msg)
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="query") from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        sdk_options = self._build_native_options(options)
        try:
            sdk_client = self._sdk.ClaudeSDKClient(options=sdk_options)
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="client_init") from e
        return _ClaudeStatefulClient(sdk_client, self._to_message)  # type: ignore[return-value]

    # ---- Translation hooks ---------------------------------------------------

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            # Claude has SystemPromptFile, but for portability we read the file
            # contents and pass as a plain string. (A future enhancement can
            # detect SystemPromptFile availability on the SDK and prefer it.)
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            # Claude supports presets via SystemPromptPreset; return the id and
            # let the build step wrap it. For our purposes we expose the id
            # as a dict with a marker so _build_native_options can recognize it.
            return {"__preset_id__": sp.preset_id}
        raise TranslationError(f"Unknown SystemPrompt subtype: {type(sp).__name__}")

    def _translate_tools(self, policy: ToolPolicy) -> dict[str, Any]:
        # Pass-through to claude_agent_sdk's allowed_tools.
        return {
            "allowed_tools": list(policy.allowed),
            # Custom tools live in extras["claude"]["custom_mcp"] if a caller
            # wants to wire in @tool-decorated handlers. Phase A keeps the
            # pass-through minimal; richer wiring lands when a caller needs it.
        }

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> dict[str, Any]:
        out: dict[str, dict[str, Any]] = {}
        for s in servers:
            entry: dict[str, Any] = {"transport": s.transport}
            if s.command is not None:
                entry["command"] = list(s.command)
            if s.url is not None:
                entry["url"] = s.url
            if s.env:
                entry["env"] = dict(s.env)
            out[s.name] = entry
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
        }
        if mcp is not None:
            kwargs["mcp_servers"] = mcp
        if options.cwd is not None:
            kwargs["cwd"] = options.cwd
        extras = options.extras.get(self.name, {}) if options.extras else {}
        if "hooks" in extras:
            kwargs["hooks"] = extras["hooks"]
        return self._sdk.ClaudeAgentOptions(**kwargs)

    def _to_message(self, sdk_msg: Any) -> Message:
        if isinstance(sdk_msg, self._sdk.ResultMessage):
            return Message(text="", is_final=True, raw=sdk_msg)
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
        async for sdk_msg in self._inner.query(prompt):
            yield self._to_message(sdk_msg)
