"""GeminiRuntime — wraps google-genai SDK.

Translates the runtime-agnostic AgentOptions into Gemini API calls.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types
from langfuse import observe

from hsb.runtime.gemini_guards import assert_gemini_oauth_only
from hsb.runtime.protocol import AgentOptions, Message, RuntimeName

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class GeminiRuntime:
    name: RuntimeName = "gemini"

    def __init__(self) -> None:
        # G1: Enforce OAuth2/ADC and project configuration.
        config = assert_gemini_oauth_only()
        
        # Initialize client with Vertex AI backend.
        self._client = genai.Client(
            vertexai=True,
            project=config["project"],
            location=config["location"],
            credentials=config["credentials"]
        )

    @observe(as_type="generation")
    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        # Hooks are now handled by the UniversalOrchestrator (Phase 2/3).
        # We ignore them here to avoid crashing, as they are now agnostic.
        
        config_kwargs: dict[str, Any] = {}
        if options.system_prompt:
            config_kwargs["system_instruction"] = options.system_prompt
        
        if options.output_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = options.output_schema

        config = types.GenerateContentConfig(**config_kwargs)

        stream = await self._client.aio.models.generate_content_stream(
            model=options.model,
            contents=prompt,
            config=config,
        )

        final_text_buffer: list[str] = []
        turns_seen = 0

        async for chunk in stream:
            # We are incrementing turns_seen here to be compatible with Codex's loop,
            # though in a true stateless query this stream is a single turn.
            text = chunk.text or ""
            if text:
                final_text_buffer.append(text)
            
            yield Message(
                text=text,
                is_final=False,
                raw=chunk,
            )

        yield Message(
            text="".join(final_text_buffer),
            is_final=True,
            raw=None,
        )

    def client(self, options: AgentOptions) -> Any:
        raise NotImplementedError(
            "GeminiRuntime.client() not yet wired — WIO port pending."
        )
