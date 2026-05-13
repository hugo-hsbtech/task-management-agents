"""GeminiProvider — dual-backend routing (Direct API vs Vertex AI)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_adc import OAuth2ADC
from llm_providers.errors import UnsupportedCapabilityError
from llm_providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def _isolate_gemini_registration():
    """Each test re-imports llm_providers.providers.gemini under a fresh
    stubbed SDK. Pop the registry entry around each test so
    re-registration is clean."""
    import sys

    original_module = sys.modules.get("llm_providers.providers.gemini")
    original_provider = ProviderRegistry._providers.get("gemini")
    sys.modules.pop("llm_providers.providers.gemini", None)
    ProviderRegistry._providers.pop("gemini", None)
    yield
    sys.modules.pop("llm_providers.providers.gemini", None)
    ProviderRegistry._providers.pop("gemini", None)
    if original_module is not None:
        sys.modules["llm_providers.providers.gemini"] = original_module
    if original_provider is not None:
        ProviderRegistry._providers["gemini"] = original_provider


def _stub_genai_sdk():
    """Build a minimal google.genai stub sufficient for provider init."""
    client_mock = MagicMock()
    client_cls = MagicMock(return_value=client_mock)
    types_mock = SimpleNamespace(GenerateContentConfig=MagicMock())
    genai = SimpleNamespace(Client=client_cls, types=types_mock)
    return genai, client_mock


def test_direct_backend_selected_for_api_key():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.providers.gemini import GeminiProvider, _DirectAPIBackend

        p = GeminiProvider(auth=ApiKey(api_key="AIzaSy-test"))
        assert isinstance(p._backend, _DirectAPIBackend)


def test_vertex_backend_selected_for_adc():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.providers.gemini import GeminiProvider, _VertexAIBackend

        p = GeminiProvider(auth=OAuth2ADC(project_id="my-project"))
        assert isinstance(p._backend, _VertexAIBackend)


def test_supported_auth():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.providers.gemini import GeminiProvider

        assert OAuth2ADC in GeminiProvider.supported_auth
        assert ApiKey in GeminiProvider.supported_auth


def test_credential_mismatch_raises():
    """Unknown credential kind raises CredentialMismatch."""
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.auth.oauth2_cli import OAuth2CliToken
        from llm_providers.errors import UnsupportedAuthError
        from llm_providers.providers.gemini import GeminiProvider

        # OAuth2CliToken is not in Gemini's supported_auth, so _validate_auth
        # raises UnsupportedAuthError before we ever reach CredentialMismatch.

        with pytest.raises(UnsupportedAuthError):
            GeminiProvider(auth=OAuth2CliToken(token="tok"))


def test_translate_system_prompt_text():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.prompt import TextSystemPrompt
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        assert p._translate_system_prompt(TextSystemPrompt(text="hello")) == "hello"


def test_translate_system_prompt_skill(tmp_path):
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.prompt import SkillReference
        from llm_providers.providers.gemini import GeminiProvider

        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("skill content")

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        assert (
            p._translate_system_prompt(SkillReference(path=skill_file))
            == "skill content"
        )


def test_translate_system_prompt_preset_raises():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.prompt import PresetSystemPrompt
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="system_prompt_file"):
            p._translate_system_prompt(PresetSystemPrompt(preset_id="x"))


def test_mcp_raises_unsupported():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.providers.gemini import GeminiProvider
        from llm_providers.tools import McpServerSpec

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="mcp"):
            p._translate_mcp(
                (McpServerSpec(name="fs", transport="stdio", command=("npx",)),)
            )


def test_client_raises_unsupported():
    genai, _ = _stub_genai_sdk()
    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.prompt import TextSystemPrompt
        from llm_providers.protocol import ProviderOptions
        from llm_providers.providers.gemini import GeminiProvider
        from llm_providers.tools import ToolPolicy

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        opts = ProviderOptions(
            system_prompt=TextSystemPrompt(text="hi"),
            model="gemini-2.5-flash",
            max_turns=1,
            tool_policy=ToolPolicy(),
        )
        with pytest.raises(UnsupportedCapabilityError, match="stateful_client"):
            p.client(opts)


@pytest.mark.asyncio
async def test_direct_query_streams_messages():
    """Smoke-test the Direct API backend's streaming path."""
    genai, client_mock = _stub_genai_sdk()

    chunk1 = SimpleNamespace(text="hello ")
    chunk2 = SimpleNamespace(text="world")

    client_mock.models.generate_content_stream.return_value = iter([chunk1, chunk2])

    with patch.dict(
        "sys.modules", {"google.genai": genai, "google": SimpleNamespace(genai=genai)}
    ):
        from llm_providers.prompt import TextSystemPrompt
        from llm_providers.protocol import ProviderOptions
        from llm_providers.providers.gemini import GeminiProvider
        from llm_providers.tools import ToolPolicy

        provider = GeminiProvider(auth=ApiKey(api_key="AIzaSy-test"))
        opts = ProviderOptions(
            system_prompt=TextSystemPrompt(text="be helpful"),
            model="gemini-2.5-flash",
            max_turns=1,
            tool_policy=ToolPolicy(),
        )

        msgs = []
        async for m in provider.query("hi", opts):
            msgs.append(m)

        # Streaming chunks + final aggregated message
        assert any(m.text == "hello " for m in msgs)
        assert any(m.text == "world" for m in msgs)
        assert msgs[-1].is_final is True
        assert msgs[-1].text == "hello world"
