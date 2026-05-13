"""OpenAIProvider — single provider, two internal backends.

- _CodexBackend: openai_codex_sdk. Operator's ChatGPT subscription quota.
                 Selected when auth resolves to oauth2_cli_token kind.
- _RawOpenAIBackend: openai SDK. Metered api.openai.com.
                     Selected when auth resolves to api_key kind.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any, ClassVar

from libs.logging import get_logger
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

logger = get_logger(__name__)


_CODEX_CAPS = Capabilities(
    supports_mcp=True,
    supports_native_tools=True,
    supports_hooks=False,
    # client() raises UnsupportedCapabilityError until WIO port (Phase C);
    # honest flag prevents callers from gating on a feature that errors at use.
    supports_stateful_client=False,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)

_RAW_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=False,
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
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (
        OAuth2CliToken,
        ApiKey,
    )

    # Pre-init placeholder; replaced by the backend-specific instance attribute
    # in __init__. Declared as ClassVar so the base-class type checker is happy.
    capabilities: ClassVar[Capabilities] = _RAW_CAPS

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
        # Shadow the ClassVar with an instance attribute carrying the
        # backend-correct capabilities. No type: ignore / @property hack.
        self.capabilities = self._backend.capabilities  # type: ignore[misc]

    async def query(  # type: ignore[override,misc]
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        try:
            async for msg in self._backend.query(prompt, options, self):
                yield msg
        except ProviderRuntimeError:
            raise
        except Exception as e:
            logger.error(
                "openai.query_failed",
                exc_type=type(e).__name__,
                error=str(e),
            )
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
        return self._backend.translate_mcp(servers, self)


class _Backend:
    """Abstract backend interface — concrete subclasses below.

    The bodies are stubs that exist purely to declare the interface for
    type checkers; concrete backends always override. The raises are
    unreachable in practice — hence ``pragma: no cover``.
    """

    capabilities: Capabilities

    async def query(  # pragma: no cover - abstract; subclasses override
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        raise NotImplementedError
        yield  # makes the function a true async generator

    def client(  # pragma: no cover - abstract; subclasses override
        self, options: ProviderOptions, provider: OpenAIProvider
    ) -> StatefulClient:
        raise NotImplementedError

    def translate_mcp(  # pragma: no cover - abstract; subclasses override
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> Any:
        raise NotImplementedError


class _CodexBackend(_Backend):
    """openai_codex_sdk backend. OAuth-only; verifies operator's ~/.codex config.

    Uses the open-source Codex CLI (subprocess-based). The legacy closed-beta
    Python SDK is no longer supported — pyproject pins ``openai-codex-sdk>=0.1.11``
    which is the open-source release.
    """

    capabilities = _CODEX_CAPS

    def __init__(self, cred: Credential) -> None:
        # The token came pre-resolved from the factory; we only need the
        # Codex home directory for config validation. Pull it from settings —
        # no env-var introspection in this module.
        from settings.codex import CodexSettings

        self._codex_home = CodexSettings().home
        self._cached_config = assert_codex_oauth_only(codex_home=self._codex_home)
        # Token kept for completeness; callers don't need it after init.
        del cred

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
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

        # Build the Codex CLI command. Subprocess inherits parent env and we
        # layer CODEX_HOME on top from settings — never mutating the parent
        # process's ``os.environ``.
        cmd = ["codex", "--quiet", "--approval-policy", str(approval).lower()]
        if options.model:
            cmd.extend(["--model", options.model])
        if options.cwd:
            cmd.extend(["--workdir", str(options.cwd)])

        # NOTE: max_turns is not enforced — the subprocess CLI has no per-turn
        # event stream, so turn tracking is unavailable on this path.
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "CODEX_HOME": str(self._codex_home)},
        )

        # All three pipes are PIPE-configured above; the asserts narrow the
        # StreamReader/Writer | None types for mypy.
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("subprocess pipes not initialised")  # pragma: no cover

        proc.stdin.write(full_text.encode())
        proc.stdin.close()

        buffer: list[str] = []
        async for line_bytes in proc.stdout:
            chunk = line_bytes.decode()
            if chunk:
                buffer.append(chunk)
                yield Message(text=chunk, is_final=False, raw=None)

        stderr_data = await proc.stderr.read()
        await proc.wait()

        if proc.returncode != 0:
            stderr_text = stderr_data.decode()
            logger.error(
                "codex.subprocess_failed",
                returncode=proc.returncode,
                stderr=stderr_text,  # full text in structured log
            )
            preview = stderr_text[:500]
            raise RuntimeError(
                f"Codex CLI failed (exit {proc.returncode}): {preview}"
                f"{' ...[truncated]' if len(stderr_text) > 500 else ''}"
            )

        yield Message(text="".join(buffer), is_final=True, raw=None)

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
        # the policy is accepted in ProviderOptions but not enforced.
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
        except Exception as e:
            logger.error(
                "openai.raw_create_failed",
                exc_type=type(e).__name__,
                error=str(e),
            )
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
