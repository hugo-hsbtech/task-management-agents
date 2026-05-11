"""HsbProviderHandle — G3 backstop wraps every message."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from hsb.runtime.handle import HsbProviderHandle
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.protocol import Message, ProviderOptions


class _FakeProvider:
    """Minimal BaseProvider stand-in for handle tests."""

    name = "fake"

    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        for m in self._messages:
            yield m

    def client(self, options: ProviderOptions) -> StatefulClient:
        return cast("StatefulClient", MagicMock())


def _make_handle(provider: _FakeProvider) -> HsbProviderHandle:
    return HsbProviderHandle(provider=cast("BaseProvider", provider), agent_name="test")


def _opts() -> ProviderOptions:
    return cast("ProviderOptions", SimpleNamespace())


async def test_query_passes_through_clean_messages() -> None:
    msgs = [Message(text="hello", is_final=False), Message(text="", is_final=True)]
    handle = _make_handle(_FakeProvider(msgs))
    received: list[Message] = []
    async for m in handle.query("hi", options=_opts()):
        received.append(m)
    assert len(received) == 2


async def test_g3_fires_on_task_tool_assistant_message(monkeypatch: Any) -> None:
    """If a message contains an AssistantMessage with a Task tool_use, G3
    raises and the iteration aborts."""
    # Build a fake AssistantMessage with a Task tool_use block.
    from claude_agent_sdk import AssistantMessage

    task_block = SimpleNamespace(name="Task")
    fake_msg = AssistantMessage.__new__(AssistantMessage)
    fake_msg.content = [task_block]  # type: ignore[list-item]

    msg_with_task = Message(text="", is_final=False, raw=fake_msg)
    msgs = [msg_with_task]
    handle = _make_handle(_FakeProvider(msgs))

    with pytest.raises(RuntimeError, match="G3 violation"):
        async for _ in handle.query("hi", options=_opts()):
            pass


def test_client_returns_provider_client() -> None:
    p = _FakeProvider([])
    handle = _make_handle(p)
    result = handle.client(options=_opts())
    assert result is not None
