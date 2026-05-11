"""ClaudeProvider — translation hooks + auth wiring with mocked SDK."""

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
    each test so re-registration is clean."""
    import sys

    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)
    yield
    sys.modules.pop("llm_providers.providers.claude", None)
    ProviderRegistry._providers.pop("claude", None)


@pytest.fixture
def provider(monkeypatch):
    """Construct ClaudeProvider with a stubbed Claude SDK."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-abc")
    fake_sdk = SimpleNamespace(
        query=MagicMock(),
        ClaudeAgentOptions=MagicMock(),
        ClaudeSDKClient=MagicMock(),
        AssistantMessage=type("AssistantMessage", (), {}),
        ResultMessage=type("ResultMessage", (), {}),
    )
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        from llm_providers.providers.claude import ClaudeProvider

        yield ClaudeProvider(auth=OAuth2CliToken(env_var="CLAUDE_CODE_OAUTH_TOKEN"))


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
    # The translated value should be the SystemPromptFile-equivalent;
    # for our stubbed SDK we check the wrapping path.
    assert hasattr(out, "path") or out == "skill content" or "skill content" in str(out)


def test_translate_preset_when_supported(provider):
    out = provider._translate_system_prompt(PresetSystemPrompt(preset_id="my-preset"))
    # Output is provider-specific; assert it's truthy (preset is supported).
    assert out is not None


def test_translate_tools_uses_allowed_list(provider):
    pol = ToolPolicy(allowed=("Read", "Bash"))
    out = provider._translate_tools(pol)
    assert out["allowed_tools"] == ["Read", "Bash"]


def test_translate_mcp_returns_dict(provider):
    spec = McpServerSpec(
        name="linear",
        transport="stdio",
        command=("npx", "linear-mcp"),
    )
    out = provider._translate_mcp((spec,))
    assert "linear" in out
    assert out["linear"]["transport"] == "stdio"


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
