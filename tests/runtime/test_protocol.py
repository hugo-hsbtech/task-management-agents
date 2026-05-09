"""Tests for the runtime-agnostic Protocol surface."""
from __future__ import annotations

import pytest
from typing import get_type_hints

from hsb.runtime.protocol import AgentOptions, Runtime, Message


def test_agent_options_is_frozen_dataclass():
    opts = AgentOptions(
        system_prompt="hi",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
    )
    with pytest.raises(Exception):
        opts.system_prompt = "modified"  # type: ignore[misc]


def test_agent_options_optional_fields_default_none():
    opts = AgentOptions(
        system_prompt="x",
        allowed_tools=(),
        permission_mode="default",
        max_turns=1,
        model="m",
    )
    assert opts.mcp_servers is None
    assert opts.cwd is None
    assert opts.output_schema is None
    assert opts.hooks is None


def test_runtime_protocol_has_required_methods():
    hints = get_type_hints(Runtime)
    assert "name" in hints
    assert hasattr(Runtime, "query")
    assert hasattr(Runtime, "client")


def test_message_has_text_field():
    msg = Message(text="hello", is_final=False)
    assert msg.text == "hello"
    assert msg.is_final is False
