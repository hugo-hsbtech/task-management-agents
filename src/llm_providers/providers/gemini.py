"""GeminiProvider — single provider, two internal backends.

- _DirectAPIBackend: google-genai SDK with api_key. Google AI Studio.
                     Selected when auth resolves to api_key kind.
- _VertexAIBackend:  google-genai SDK with vertexai=True. Vertex AI.
                     Selected when auth resolves to oauth2_adc kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from libs.logging import get_logger
from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_adc import OAuth2ADC
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
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

_DIRECT_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=False,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)

_VERTEX_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=False,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)


@ProviderRegistry.register("gemini")
class GeminiProvider(BaseProvider):
    """Gemini provider with two internal backends selected by auth kind.

    Recognized ProviderOptions.extras["gemini"] keys:
      - "project_id": GCP project for Vertex AI backend
      - "location":   GCP region (default: us-central1)
    """

    name: ClassVar[str] = "gemini"
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (
        OAuth2ADC,
        ApiKey,
    )

    # Pre-init placeholder; replaced by the backend-specific instance attribute
    # in __init__. Declared as ClassVar so the base-class type checker is happy.
    capabilities: ClassVar[Capabilities] = _DIRECT_CAPS

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        cred = self._auth.resolve()
        if cred.kind == "oauth2_adc":
            self._backend: _Backend = _VertexAIBackend(cred)
        elif cred.kind == "api_key":
            self._backend = _DirectAPIBackend(cred)
        else:
            raise CredentialMismatch(
                f"GeminiProvider cannot apply credential kind {cred.kind!r}"
            )
        # Shadow the ClassVar with an instance attribute carrying the
        # backend-correct capabilities.
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
                "gemini.query_failed",
                exc_type=type(e).__name__,
                error=str(e),
            )
            raise ProviderRuntimeError(provider=self.name, phase="query") from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=self.name,
            capability="stateful_client (Gemini: not wired in Phase B)",
        )

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
        if servers:
            raise UnsupportedCapabilityError(provider=self.name, capability="mcp")
        return None


class _Backend:
    """Abstract backend interface — concrete subclasses below."""

    capabilities: Capabilities

    async def query(  # pragma: no cover - abstract; subclasses override
        self, prompt: str, options: ProviderOptions, provider: GeminiProvider
    ) -> AsyncIterator[Message]:
        raise NotImplementedError
        yield  # makes the function a true async generator

    def client(  # pragma: no cover - abstract; subclasses override
        self, options: ProviderOptions, provider: GeminiProvider
    ) -> StatefulClient:
        raise NotImplementedError


class _DirectAPIBackend(_Backend):
    """google-genai SDK backend with API key. Google AI Studio."""

    capabilities = _DIRECT_CAPS

    def __init__(self, cred: Credential) -> None:
        from google import genai  # lazy import

        self._client = genai.Client(api_key=cred.payload["api_key"])

    async def query(
        self, prompt: str, options: ProviderOptions, provider: GeminiProvider
    ) -> AsyncIterator[Message]:
        sp_text = provider._translate_system_prompt(options.system_prompt)

        config: dict[str, Any] = {}
        if sp_text:
            config["system_instruction"] = sp_text
        if options.output_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = options.output_schema

        from google.genai import types  # lazy import

        generate_config = types.GenerateContentConfig(**config)

        response = self._client.models.generate_content_stream(
            model=options.model,
            contents=prompt,
            config=generate_config,
        )

        buffer: list[str] = []
        for chunk in response:
            text = chunk.text or ""
            buffer.append(text)
            yield Message(text=text, is_final=False, raw=chunk)
        yield Message(text="".join(buffer), is_final=True, raw=None)

    def client(
        self, options: ProviderOptions, provider: GeminiProvider
    ) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (Direct API backend: not wired)",
        )


class _VertexAIBackend(_Backend):
    """google-genai SDK backend with Vertex AI via ADC."""

    capabilities = _VERTEX_CAPS

    def __init__(self, cred: Credential) -> None:
        import os

        from google import genai  # lazy import

        self._project = (
            cred.payload.get("project_id")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCLOUD_PROJECT")
        )
        if not self._project:
            raise ProviderRuntimeError(
                provider="gemini",
                phase="init",
                detail=(
                    "Vertex AI backend requires a GCP project ID. "
                    "Set GOOGLE_CLOUD_PROJECT env var or pass project_id "
                    "via OAuth2ADC(project_id='...')."
                ),
            )
        self._client = genai.Client(
            vertexai=True,
            project=self._project,
            location="us-central1",
        )

    async def query(
        self, prompt: str, options: ProviderOptions, provider: GeminiProvider
    ) -> AsyncIterator[Message]:
        sp_text = provider._translate_system_prompt(options.system_prompt)

        # Allow per-call overrides from extras["gemini"]
        extras = options.extras.get("gemini", {}) if options.extras else {}
        if "location" in extras or "project_id" in extras:
            from google import genai  # lazy import

            self._client = genai.Client(
                vertexai=True,
                project=extras.get("project_id", self._project),
                location=extras.get("location", "us-central1"),
            )

        config: dict[str, Any] = {}
        if sp_text:
            config["system_instruction"] = sp_text
        if options.output_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = options.output_schema

        from google.genai import types  # lazy import

        generate_config = types.GenerateContentConfig(**config)

        response = self._client.models.generate_content_stream(
            model=options.model,
            contents=prompt,
            config=generate_config,
        )

        buffer: list[str] = []
        for chunk in response:
            text = chunk.text or ""
            buffer.append(text)
            yield Message(text=text, is_final=False, raw=chunk)
        yield Message(text="".join(buffer), is_final=True, raw=None)

    def client(
        self, options: ProviderOptions, provider: GeminiProvider
    ) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (Vertex AI backend: not wired)",
        )
