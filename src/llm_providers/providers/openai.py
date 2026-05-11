"""OpenAIProvider — single provider, two internal backends.

- _CodexBackend: openai_codex_sdk. Operator's ChatGPT subscription quota.
                 Selected when auth resolves to oauth2_cli_token kind.
- _RawOpenAIBackend: openai SDK. Metered api.openai.com.
                     Selected when auth resolves to api_key kind.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import (
    CredentialMismatch,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedCapabilityError,
)
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)
from llm_providers.providers._codex_config import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _CodexOAuth2CliToken(OAuth2CliToken):
    """OAuth2 token pre-wired to ~/.codex/auth.json (honoring CODEX_HOME) for
    auto-detection."""

    @classmethod
    def default(cls) -> _CodexOAuth2CliToken:
        codex_home = os.environ.get("CODEX_HOME")
        base = Path(codex_home) if codex_home else Path.home() / ".codex"
        return cls(token_path=base / "auth.json")


class _OpenAIApiKey(ApiKey):
    """ApiKey pre-wired to OPENAI_API_KEY for auto-detection."""

    @classmethod
    def default(cls) -> _OpenAIApiKey:
        return cls(env_var="OPENAI_API_KEY")


_CODEX_CAPS = Capabilities(
    supports_mcp=True,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=True,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)

_RAW_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=True,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)


_PERMISSION_MAP: dict[PermissionMode, str] = {
    "default": "on-request",
    "acceptEdits": "never",
    "plan": "on-request",
    "bypassPermissions": "never",
}


@ProviderRegistry.register("openai")
class OpenAIProvider(BaseProvider):
    """OpenAI provider with two internal backends selected by auth kind.

    Recognized ProviderOptions.extras["openai"] keys: none in Phase A.
    """

    name: ClassVar[str] = "openai"
    # Class-level placeholder; overridden by instance property below.
    capabilities: ClassVar[Capabilities] = _RAW_CAPS
    # _CodexOAuth2CliToken / _OpenAIApiKey appear first so auto_resolve_auth
    # walks their pre-wired default() (which knows where to look for tokens).
    # OAuth2CliToken / ApiKey remain in the tuple so callers constructing
    # them directly (e.g. tests, explicit wiring) still satisfy
    # _validate_auth's isinstance check.
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (
        _CodexOAuth2CliToken,
        _OpenAIApiKey,
        OAuth2CliToken,
        ApiKey,
    )

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        cred = self._auth.resolve()
        if cred.kind == "oauth2_cli_token":
            self._backend: _Backend = _CodexBackend(cred)
        elif cred.kind == "api_key":
            self._backend = _RawOpenAIBackend(cred)
        else:
            raise CredentialMismatch(
                f"OpenAIProvider cannot apply credential kind {cred.kind!r}"
            )

    @property  # type: ignore[no-redef]
    def capabilities(self) -> Capabilities:  # type: ignore[override]  # noqa: F811
        return self._backend.capabilities

    async def query(  # type: ignore[override,misc]
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        try:
            async for msg in self._backend.query(prompt, options, self):
                yield msg
        except ProviderRuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="query") from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        return self._backend.client(options, self)

    # ---- Translation hooks (shared across backends) --------------------------

    def _translate_system_prompt(self, sp: SystemPrompt) -> str:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            raise UnsupportedCapabilityError(
                provider=self.name, capability="system_prompt_file"
            )
        raise TranslationError(f"Unknown SystemPrompt subtype: {type(sp).__name__}")

    def _translate_tools(self, policy: ToolPolicy) -> dict[str, Any]:
        return {"allowed_tools": list(policy.allowed)}

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> Any:
        # Backend decides whether MCP is supported. Codex verifies operator
        # config; raw OpenAI raises UnsupportedCapabilityError.
        return self._backend.translate_mcp(servers, self)


class _Backend:
    """Common backend interface — shared shape; implementations differ."""

    capabilities: Capabilities

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        raise NotImplementedError
        yield  # pragma: no cover  (makes mypy treat this as an async generator)

    def client(
        self, options: ProviderOptions, provider: OpenAIProvider
    ) -> StatefulClient:
        raise NotImplementedError

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> Any:
        raise NotImplementedError


class _CodexBackend(_Backend):
    """openai_codex_sdk backend. OAuth-only; verifies operator's ~/.codex config."""

    capabilities = _CODEX_CAPS

    def __init__(self, cred: Credential) -> None:
        # cred.payload["source"] is "env:..." or "file:<path>" — for "file:" we
        # derive codex_home from the file's parent for the config verification.
        source = cred.payload.get("source", "")
        codex_home: Path | None = None
        if source.startswith("file:"):
            codex_home = Path(source.removeprefix("file:")).parent
        self._cached_config = assert_codex_oauth_only(codex_home=codex_home)
        import openai_codex_sdk

        self._sdk = openai_codex_sdk
        self._codex_home = codex_home

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        # NOTE: options.tool_policy.allowed/denied/custom is currently a no-op
        # on the OpenAI provider. Codex tool surface (Phase B) and OpenAI
        # function-calling translation (Phase B) will wire this in. For Phase A,
        # the policy is accepted in ProviderOptions but not enforced — callers
        # that depend on tool restriction should not yet flip an agent to
        # HSB_RUNTIME_<AGENT>=openai.
        if options.mcp_servers:
            verify_codex_mcp(self._cached_config, [s.name for s in options.mcp_servers])

        approval = _PERMISSION_MAP.get(options.permission_mode)
        if approval is None:
            raise UnsupportedCapabilityError(
                provider=provider.name,
                capability=f"permission_mode={options.permission_mode}",
            )

        sp_text = provider._translate_system_prompt(options.system_prompt)
        full_text = f"<system>{sp_text}</system>\n\n{prompt}"

        thread_options = self._sdk.ThreadOptions(
            model=options.model,
            approvalPolicy=approval,  # type: ignore[arg-type]
            workingDirectory=options.cwd,
        )
        turn_options = self._sdk.TurnOptions(outputSchema=options.output_schema)

        codex_opts = self._build_codex_options()
        codex = (
            self._sdk.Codex(codex_opts) if codex_opts is not None else self._sdk.Codex()
        )
        thread = codex.start_thread(thread_options)
        streamed = await thread.run_streamed(
            [self._sdk.TextInput(type="text", text=full_text)],
            turn_options,
        )

        turns_seen = 0
        final_buffer: list[str] = []
        async for evt in streamed.events:
            if isinstance(
                evt, self._sdk.TurnCompletedEvent | self._sdk.TurnFailedEvent
            ):
                turns_seen += 1
                if turns_seen > options.max_turns:
                    raise RuntimeError(
                        f"Codex exceeded max_turns={options.max_turns}; aborting."
                    )
            evt_text = self._extract_event_text(evt)
            if evt_text:
                final_buffer.append(evt_text)
            yield Message(text=evt_text, is_final=False, raw=evt)

        yield Message(text="".join(final_buffer), is_final=True, raw=None)

    def client(
        self, options: ProviderOptions, provider: OpenAIProvider
    ) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (Codex backend: not wired in Phase A)",
        )

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> dict[str, dict[str, Any]]:
        # Codex MCP is operator-managed in ~/.codex/config.toml. We verify the
        # requested names are present and return the resolved blocks for
        # visibility; we do NOT write to the operator's config.
        verify_codex_mcp(self._cached_config, [s.name for s in servers])
        return {s.name: self._cached_config["mcp_servers"][s.name] for s in servers}

    @staticmethod
    def _extract_event_text(evt: Any) -> str:
        direct = getattr(evt, "text", None)
        if isinstance(direct, str) and direct:
            return direct
        item = getattr(evt, "item", None)
        if item is not None:
            item_text = getattr(item, "text", None)
            if isinstance(item_text, str) and item_text:
                return item_text
        return ""

    def _build_codex_options(self) -> Any:
        from openai_codex_sdk.types import CodexOptions

        override = os.environ.get("CODEX_PATH_OVERRIDE")
        if override:
            return CodexOptions(codexPathOverride=override)
        return None


class _RawOpenAIBackend(_Backend):
    """openai SDK backend. API-key-based; no MCP support."""

    capabilities = _RAW_CAPS

    def __init__(self, cred: Credential) -> None:
        import openai

        self._sdk = openai
        self._client = openai.AsyncOpenAI(api_key=cred.payload["api_key"])

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        # NOTE: options.tool_policy.allowed/denied/custom is currently a no-op
        # on the OpenAI provider. Codex tool surface (Phase B) and OpenAI
        # function-calling translation (Phase B) will wire this in. For Phase A,
        # the policy is accepted in ProviderOptions but not enforced — callers
        # that depend on tool restriction should not yet flip an agent to
        # HSB_RUNTIME_<AGENT>=openai.
        sp_text = provider._translate_system_prompt(options.system_prompt)
        messages = [
            {"role": "system", "content": sp_text},
            {"role": "user", "content": prompt},
        ]
        try:
            stream = await self._client.chat.completions.create(
                model=options.model,
                messages=messages,
                stream=True,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=provider.name, phase="query") from e

        final_buffer: list[str] = []
        async for chunk in stream:
            chunk_text = ""
            for choice in chunk.choices:
                delta = getattr(choice, "delta", None)
                if delta is not None:
                    chunk_text += getattr(delta, "content", "") or ""
            if chunk_text:
                final_buffer.append(chunk_text)
            yield Message(text=chunk_text, is_final=False, raw=chunk)
        yield Message(text="".join(final_buffer), is_final=True, raw=None)

    def client(
        self, options: ProviderOptions, provider: OpenAIProvider
    ) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (raw OpenAI backend: not wired in Phase A)",
        )

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> Any:
        if servers:
            raise UnsupportedCapabilityError(provider=provider.name, capability="mcp")
        return None
