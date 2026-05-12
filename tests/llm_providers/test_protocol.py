"""Shape/invariant tests for protocol types."""

from __future__ import annotations

import pytest

from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)


def test_message_is_frozen():
    m = Message(text="hi", is_final=True, raw=None)
    with pytest.raises(Exception):  # noqa: B017  # frozen dataclass raises FrozenInstanceError
        m.text = "x"  # type: ignore[misc]


def test_message_defaults():
    m = Message(text="hi")
    assert m.is_final is False
    assert m.raw is None


def test_capabilities_is_frozen():
    c = Capabilities(
        supports_mcp=True,
        supports_native_tools=True,
        supports_hooks=False,
        supports_stateful_client=True,
        supports_output_schema=True,
        supports_system_prompt_file=True,
        supports_streaming=True,
    )
    with pytest.raises(Exception):  # noqa: B017  # frozen dataclass raises FrozenInstanceError
        c.supports_mcp = False  # type: ignore[misc]
    assert c.max_context_tokens is None


def test_provider_options_required_fields():
    from llm_providers.prompt import TextSystemPrompt
    from llm_providers.tools import ToolPolicy

    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="m",
        max_turns=5,
        tool_policy=ToolPolicy(),
    )
    assert opts.mcp_servers == ()
    assert opts.permission_mode == "default"
    assert opts.output_schema is None
    assert opts.cwd is None
    assert opts.extras == {}


def test_permission_mode_literal_values():
    # PermissionMode is a Literal; test that valid values type-check at runtime
    # (we can't introspect Literals easily without typing helpers, so this is
    # a smoke test that the import works and a known value is accepted).
    opts: PermissionMode = "default"
    assert opts == "default"
