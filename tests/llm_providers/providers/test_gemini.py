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


def _patch_sdk(genai):
    """Return a context manager that patches sys.modules with the SDK stub."""
    return patch.dict(
        "sys.modules",
        {"google.genai": genai, "google": SimpleNamespace(genai=genai)},
    )


def _make_opts(model="gemini-2.5-flash", **kwargs):
    """Build a minimal ProviderOptions for tests."""
    from llm_providers.prompt import TextSystemPrompt
    from llm_providers.protocol import ProviderOptions
    from llm_providers.tools import ToolPolicy

    return ProviderOptions(
        system_prompt=TextSystemPrompt(text="be helpful"),
        model=model,
        max_turns=1,
        tool_policy=ToolPolicy(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def test_direct_backend_selected_for_api_key():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider, _DirectAPIBackend

        p = GeminiProvider(auth=ApiKey(api_key="AIzaSy-test"))
        assert isinstance(p._backend, _DirectAPIBackend)


def test_vertex_backend_selected_for_adc():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider, _VertexAIBackend

        p = GeminiProvider(auth=OAuth2ADC(project_id="my-project"))
        assert isinstance(p._backend, _VertexAIBackend)


def test_supported_auth():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        assert OAuth2ADC in GeminiProvider.supported_auth
        assert ApiKey in GeminiProvider.supported_auth


def test_unsupported_auth_raises():
    """OAuth2CliToken is not in Gemini's supported_auth."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.auth.oauth2_cli import OAuth2CliToken
        from llm_providers.errors import UnsupportedAuthError
        from llm_providers.providers.gemini import GeminiProvider

        with pytest.raises(UnsupportedAuthError):
            GeminiProvider(auth=OAuth2CliToken(token="tok"))


def test_credential_mismatch_raises():
    """If _validate_auth is bypassed, CredentialMismatch is raised."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.auth.base import AuthStrategy, Credential
        from llm_providers.errors import CredentialMismatch
        from llm_providers.providers.gemini import GeminiProvider

        class _FakeAuth(AuthStrategy):
            kind = "_fake_kind"

            def resolve(self):
                return Credential(kind="_fake_kind", payload={})

        # Bypass _validate_auth by adding _FakeAuth to supported_auth
        original = GeminiProvider.supported_auth
        GeminiProvider.supported_auth = (*original, _FakeAuth)
        try:
            with pytest.raises(CredentialMismatch, match="_fake_kind"):
                GeminiProvider(auth=_FakeAuth())
        finally:
            GeminiProvider.supported_auth = original


# ---------------------------------------------------------------------------
# Translation hooks
# ---------------------------------------------------------------------------


def test_translate_system_prompt_text():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.prompt import TextSystemPrompt
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        assert p._translate_system_prompt(TextSystemPrompt(text="hello")) == "hello"


def test_translate_system_prompt_skill(tmp_path):
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
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
    with _patch_sdk(genai):
        from llm_providers.prompt import PresetSystemPrompt
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="system_prompt_file"):
            p._translate_system_prompt(PresetSystemPrompt(preset_id="x"))


def test_translate_system_prompt_unknown_raises():
    """Unknown SystemPrompt subtype raises TranslationError."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.errors import TranslationError
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(TranslationError, match="Unknown SystemPrompt"):
            p._translate_system_prompt("not a SystemPrompt")  # type: ignore[arg-type]


def test_translate_tools():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider
        from llm_providers.tools import ToolPolicy

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        policy = ToolPolicy(allowed=frozenset({"tool_a", "tool_b"}))
        result = p._translate_tools(policy)
        assert set(result["allowed_tools"]) == {"tool_a", "tool_b"}


def test_mcp_empty_returns_none():
    """Empty MCP servers returns None without raising."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        assert p._translate_mcp(()) is None


def test_mcp_raises_unsupported():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider
        from llm_providers.tools import McpServerSpec

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="mcp"):
            p._translate_mcp(
                (McpServerSpec(name="fs", transport="stdio", command=("npx",)),)
            )


# ---------------------------------------------------------------------------
# Direct API backend
# ---------------------------------------------------------------------------


def test_client_raises_unsupported():
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="stateful_client"):
            p.client(_make_opts())


def test_direct_backend_client_raises():
    """Direct backend's own client() raises."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=ApiKey(api_key="k"))
        with pytest.raises(UnsupportedCapabilityError, match="Direct API"):
            p._backend.client(_make_opts(), p)


@pytest.mark.asyncio
async def test_direct_query_streams_messages():
    """Smoke-test the Direct API backend's streaming path."""
    genai, client_mock = _stub_genai_sdk()

    chunk1 = SimpleNamespace(text="hello ")
    chunk2 = SimpleNamespace(text="world")

    client_mock.models.generate_content_stream.return_value = iter([chunk1, chunk2])

    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=ApiKey(api_key="AIzaSy-test"))

        msgs = []
        async for m in provider.query("hi", _make_opts()):
            msgs.append(m)

        # Streaming chunks + final aggregated message
        assert any(m.text == "hello " for m in msgs)
        assert any(m.text == "world" for m in msgs)
        assert msgs[-1].is_final is True
        assert msgs[-1].text == "hello world"


@pytest.mark.asyncio
async def test_direct_query_with_output_schema():
    """Output schema sets response_mime_type and response_schema."""
    genai, client_mock = _stub_genai_sdk()

    chunk = SimpleNamespace(text='{"answer": 42}')
    client_mock.models.generate_content_stream.return_value = iter([chunk])

    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=ApiKey(api_key="k"))
        opts = _make_opts(output_schema={"type": "object"})

        msgs = []
        async for m in provider.query("hi", opts):
            msgs.append(m)

        assert msgs[-1].is_final is True
        # Verify GenerateContentConfig was called with the schema config
        config_cls = genai.types.GenerateContentConfig
        call_kwargs = config_cls.call_args[1]
        assert call_kwargs["response_mime_type"] == "application/json"
        assert call_kwargs["response_schema"] == {"type": "object"}


@pytest.mark.asyncio
async def test_query_wraps_unexpected_exception():
    """Non-ProviderRuntimeError exceptions are wrapped."""
    genai, client_mock = _stub_genai_sdk()

    client_mock.models.generate_content_stream.side_effect = ConnectionError("boom")

    with _patch_sdk(genai):
        from llm_providers.errors import ProviderRuntimeError
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=ApiKey(api_key="k"))

        with pytest.raises(ProviderRuntimeError, match="query") as exc_info:
            async for _ in provider.query("hi", _make_opts()):
                pass

        assert isinstance(exc_info.value.__cause__, ConnectionError)


@pytest.mark.asyncio
async def test_query_passes_provider_runtime_error_through():
    """ProviderRuntimeError is re-raised without wrapping."""
    genai, client_mock = _stub_genai_sdk()

    from llm_providers.errors import ProviderRuntimeError

    original = ProviderRuntimeError(provider="gemini", phase="inner")
    client_mock.models.generate_content_stream.side_effect = original

    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=ApiKey(api_key="k"))

        with pytest.raises(ProviderRuntimeError) as exc_info:
            async for _ in provider.query("hi", _make_opts()):
                pass

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# Vertex AI backend
# ---------------------------------------------------------------------------


def test_vertex_missing_project_raises(monkeypatch):
    """VertexAI backend requires project ID — raises clearly."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.errors import ProviderRuntimeError
        from llm_providers.providers.gemini import GeminiProvider

        with pytest.raises(ProviderRuntimeError, match="GOOGLE_CLOUD_PROJECT"):
            GeminiProvider(auth=OAuth2ADC())


def test_vertex_reads_project_from_env(monkeypatch):
    """VertexAI backend reads GOOGLE_CLOUD_PROJECT from env."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider, _VertexAIBackend

        p = GeminiProvider(auth=OAuth2ADC())
        assert isinstance(p._backend, _VertexAIBackend)
        assert p._backend._project == "env-project"


def test_vertex_client_raises():
    """Vertex backend's client() raises unsupported."""
    genai, _ = _stub_genai_sdk()
    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        p = GeminiProvider(auth=OAuth2ADC(project_id="proj"))
        with pytest.raises(UnsupportedCapabilityError, match="Vertex AI"):
            p._backend.client(_make_opts(), p)


@pytest.mark.asyncio
async def test_vertex_query_streams_messages():
    """Smoke-test the Vertex AI backend's streaming path."""
    genai, client_mock = _stub_genai_sdk()

    chunk1 = SimpleNamespace(text="vertex ")
    chunk2 = SimpleNamespace(text="reply")

    client_mock.models.generate_content_stream.return_value = iter([chunk1, chunk2])

    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=OAuth2ADC(project_id="proj"))

        msgs = []
        async for m in provider.query("hi", _make_opts()):
            msgs.append(m)

        assert any(m.text == "vertex " for m in msgs)
        assert msgs[-1].is_final is True
        assert msgs[-1].text == "vertex reply"


@pytest.mark.asyncio
async def test_vertex_query_with_extras_overrides():
    """Extras["gemini"] overrides location/project per-call."""
    genai, client_mock = _stub_genai_sdk()

    chunk = SimpleNamespace(text="ok")
    client_mock.models.generate_content_stream.return_value = iter([chunk])

    with _patch_sdk(genai):
        from llm_providers.providers.gemini import GeminiProvider

        provider = GeminiProvider(auth=OAuth2ADC(project_id="proj"))
        opts = _make_opts(
            extras={"gemini": {"location": "europe-west1", "project_id": "other-proj"}},
        )

        msgs = []
        async for m in provider.query("hi", opts):
            msgs.append(m)

        assert msgs[-1].is_final is True
        # Verify Client was re-created with the override values
        calls = genai.Client.call_args_list
        last_call = calls[-1]
        assert last_call[1]["project"] == "other-proj"
        assert last_call[1]["location"] == "europe-west1"
