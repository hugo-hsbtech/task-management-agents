"""HsbProviderHandle — seam where hsb-side policy wraps the library provider.

Today: applies G3 (Task-tool runtime backstop) to every message yielded by
the wrapped provider.query() iterator. Future hsb-only guards (e.g. G6
auditing) plug in here without touching the library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.protocol import Message, ProviderOptions

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass(frozen=True)
class HsbProviderHandle:
    """Wraps a BaseProvider and applies hsb-side runtime policy."""

    provider: BaseProvider
    agent_name: str

    @property
    def name(self) -> str:
        return self.provider.name

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        from hsb.agents._sdk_options import assert_no_task_dispatch

        async for msg in self.provider.query(prompt, options):  # type: ignore[attr-defined]
            # G3 backstop: assert_no_task_dispatch inspects raw SDK messages.
            # If msg.raw is None (e.g. synthetic final), skip.
            if msg.raw is not None:
                assert_no_task_dispatch(msg.raw)
            yield msg

    def client(self, options: ProviderOptions) -> StatefulClient:
        return self.provider.client(options)
