"""ClaudeProvider — translation hooks + auth wiring with mocked SDK."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import UnsupportedAuthError
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    TextSystemPrompt,
)
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


@pytest.fixture(autouse=True)
def _isolate_claude_registration():
    """Each test re-imports llm_providers.providers.claude under a fresh
    stubbed claude_agent_sdk. patch.dict("sys.modules", ...) evicts the
    re-imported module on exit, so the decorator re-runs the next time —
    which would collide with the prior registration. Pop the entry around
    each test so re-registration is clean, then restore BOTH the registry
    entry and sys.modules afterwards. sys.modules must be restored together
    with the registry: if a later test re-imports the provider module while
    the registry already has it, the @register decorator raises 'already
    registered'."""
    import sys

    original_module = sys.modules.get("llm_providers.providers.claude")
    original_provider = ProviderRegistry._providers.get("claude")
    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)
    yield
    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)
    if original_module is not None:
        sys.modules["llm_providers.providers.claude"] = original_module
    if original_provider is not None:
        ProviderRegistry._providers["claude"] = original_provider


@pytest.fixture
def provider():
    """Construct ClaudeProvider with a stubbed Claude SDK."""
    fake_sdk = SimpleNamespace(
        query=MagicMock(),
        ClaudeAgentOptions=MagicMock(),
        ClaudeSDKClient=MagicMock(),
        AssistantMessage=type("AssistantMessage", (), {}),
        ResultMessage=type("ResultMessage", (), {}),
    )
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        from llm_providers.providers.claude import ClaudeProvider

        yield ClaudeProvider(auth=OAuth2CliToken(token="tok-abc"))


def test_capabilities_declared():
    with patch.dict(
        "sys.modules",
        {
            "claude_agent_sdk": SimpleNamespace(
                ClaudeAgentOptions=MagicMock(),
                ClaudeSDKClient=MagicMock(),
                query=MagicMock(),
                AssistantMessage=type("X", (), {}),
                ResultMessage=type("Y", (), {}),
            )
        },
    ):
        from llm_providers.providers.claude import ClaudeProvider
    caps = ClaudeProvider.capabilities
    assert caps.supports_mcp is True
    assert caps.supports_native_tools is True
    assert caps.supports_hooks is True
    assert caps.supports_stateful_client is True
    assert caps.supports_output_schema is True
    assert caps.supports_system_prompt_file is True
    assert caps.supports_streaming is True


def test_supported_auth():
    with patch.dict(
        "sys.modules",
        {
            "claude_agent_sdk": SimpleNamespace(
                ClaudeAgentOptions=MagicMock(),
                ClaudeSDKClient=MagicMock(),
                query=MagicMock(),
                AssistantMessage=type("X", (), {}),
                ResultMessage=type("Y", (), {}),
            )
        },
    ):
        from llm_providers.providers.claude import ClaudeProvider
    assert OAuth2CliToken in ClaudeProvider.supported_auth
    assert ApiKey in ClaudeProvider.supported_auth


def test_translate_text_system_prompt(provider):
    out = provider._translate_system_prompt(TextSystemPrompt(text="hi"))
    assert out == "hi"


def test_translate_skill_reference_to_systempromptfile(provider, tmp_path):
    f = tmp_path / "skill.md"
    f.write_text("skill content")
    out = provider._translate_system_prompt(SkillReference(path=f))
    # The translated value is the file contents as a string (see provider impl).
    assert out == "skill content"


def test_translate_preset_when_supported(provider):
    out = provider._translate_system_prompt(PresetSystemPrompt(preset_id="my-preset"))
    # Output is provider-specific; assert it's truthy (preset is supported).
    assert out is not None


def test_translate_tools_uses_allowed_list(provider):
    pol = ToolPolicy(allowed=("Read", "Bash"))
    out = provider._translate_tools(pol)
    assert out["allowed_tools"] == ["Read", "Bash"]


def test_build_native_options_translates_output_schema_to_output_format(provider):
    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="claude-sonnet-4-6",
        max_turns=5,
        tool_policy=ToolPolicy(),
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )

    provider._build_native_options(opts)

    kwargs = provider._sdk.ClaudeAgentOptions.call_args.kwargs
    assert "output_schema" not in kwargs
    assert kwargs["output_format"] == {
        "type": "json_schema",
        "schema": opts.output_schema,
    }


def test_translate_mcp_returns_dict(provider):
    spec = McpServerSpec(
        name="linear",
        transport="stdio",
        command=("npx", "linear-mcp"),
    )
    out = provider._translate_mcp((spec,))
    assert "linear" in out
    assert out["linear"]["transport"] == "stdio"
    assert out["linear"]["command"] == "npx"
    assert out["linear"]["args"] == ["linear-mcp"]


def test_translate_mcp_rejects_stdio_without_command(provider):
    """stdio transport requires a command; missing command raises."""
    from llm_providers.errors import TranslationError

    bad = McpServerSpec(name="broken", transport="stdio", command=None)
    with pytest.raises(TranslationError, match="stdio.*command"):
        provider._translate_mcp((bad,))


def test_translate_mcp_rejects_http_without_url(provider):
    """http transport requires a url; missing url raises."""
    from llm_providers.errors import TranslationError

    bad = McpServerSpec(name="broken", transport="http", url=None)
    with pytest.raises(TranslationError, match="http.*url"):
        provider._translate_mcp((bad,))


def test_translate_preset_returns_systempromptpreset_typeddict(provider):
    """PresetSystemPrompt must produce the SDK's SystemPromptPreset shape
    (TypedDict with type='preset' and preset=<id>), not an internal marker
    dict that ClaudeAgentOptions cannot consume."""
    out = provider._translate_system_prompt(PresetSystemPrompt(preset_id="claude_code"))
    assert isinstance(out, dict)
    assert out["type"] == "preset"
    assert out["preset"] == "claude_code"
    assert "__preset_id__" not in out


def test_query_yields_messages(provider):
    """Smoke test: the query coroutine runs and yields at least one Message."""
    # Configure stubbed SDK to yield one assistant + one result.
    import asyncio

    sdk = pytest.importorskip("claude_agent_sdk")
    msg_assistant = MagicMock(spec=sdk.AssistantMessage)
    msg_assistant.content = [SimpleNamespace(text="hello")]
    msg_result = MagicMock(spec=sdk.ResultMessage)

    async def _aiter():
        yield msg_assistant
        yield msg_result

    sdk.query.return_value = _aiter()
    pol = ToolPolicy(allowed=())
    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="claude-sonnet-4-6",
        max_turns=5,
        tool_policy=pol,
    )

    async def _run():
        msgs = []
        async for m in provider.query("hi", opts):
            msgs.append(m)
        return msgs

    msgs = asyncio.run(_run())
    assert any(isinstance(m, Message) for m in msgs)
    assert any(m.is_final for m in msgs)


def test_result_message_prefers_structured_output(provider):
    sdk = pytest.importorskip("claude_agent_sdk")
    msg_result = MagicMock(spec=sdk.ResultMessage)
    msg_result.subtype = "success"
    msg_result.structured_output = {"ok": True}
    msg_result.result = None

    message = provider._to_message(msg_result)

    assert message.is_final is True
    assert json.loads(message.text) == {"ok": True}


def test_stateful_client_query_converts_messages(provider):
    """_ClaudeStatefulClient.query must delegate Message conversion to _to_message,
    so AssistantMessage text is extracted and ResultMessage is marked is_final."""
    import asyncio

    sdk = pytest.importorskip("claude_agent_sdk")
    msg_assistant = MagicMock(spec=sdk.AssistantMessage)
    msg_assistant.content = [
        SimpleNamespace(text="hello"),
        SimpleNamespace(text=" world"),
    ]
    msg_result = MagicMock(spec=sdk.ResultMessage)

    async def _aiter(_prompt):
        yield msg_assistant
        yield msg_result

    fake_sdk_client = MagicMock()
    fake_sdk_client.query = _aiter
    sdk.ClaudeSDKClient.return_value = fake_sdk_client

    pol = ToolPolicy(allowed=())
    opts = ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model="claude-sonnet-4-6",
        max_turns=5,
        tool_policy=pol,
    )

    async def _run():
        stateful = provider.client(opts)
        msgs = []
        async for m in stateful.query("hi"):
            msgs.append(m)
        return msgs

    msgs = asyncio.run(_run())
    assert len(msgs) == 2
    assert msgs[0].text == "hello world"
    assert msgs[0].is_final is False
    assert msgs[1].is_final is True


def test_rejects_non_supported_auth(monkeypatch):
    from llm_providers.auth.base import AuthStrategy, Credential

    class _Other(AuthStrategy):
        kind = "other"

        def detect(self) -> bool:
            return True

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls):
            return cls()

    with patch.dict(
        "sys.modules",
        {
            "claude_agent_sdk": SimpleNamespace(
                ClaudeAgentOptions=MagicMock(),
                ClaudeSDKClient=MagicMock(),
                query=MagicMock(),
                AssistantMessage=type("X", (), {}),
                ResultMessage=type("Y", (), {}),
            )
        },
    ):
        from llm_providers.providers.claude import ClaudeProvider

        with pytest.raises(UnsupportedAuthError):
            ClaudeProvider(auth=_Other())
