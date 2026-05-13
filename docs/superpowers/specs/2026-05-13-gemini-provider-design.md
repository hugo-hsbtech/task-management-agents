# Gemini Provider — Design

**Date:** 2026-05-13
**Status:** Spec — implementation plan at `docs/superpowers/plans/2026-05-13-gemini-provider.md`
**Depends on:** Phase A — Multi-Provider Module (`docs/superpowers/specs/2026-05-11-multi-provider-module-design.md`)

---

## 1. Goal

Add Gemini as the third registered provider in `src/llm_providers/`, supporting two authentication modes: API key (Google AI Studio) and OAuth2 ADC (Vertex AI). The implementation follows the dual-backend pattern established by `OpenAIProvider` in Phase A.

## 2. Non-goals

- **OAuth2 CLI token for Gemini.** No official gemini-cli exists yet; deferred until one ships.
- **Service account JSON strategy.** `OAuth2ServiceAccount` is in the Phase A spec but deferred — ADC covers the same GCP use case via `GOOGLE_APPLICATION_CREDENTIALS`.
- **MCP support.** Gemini does not support MCP natively; `supports_mcp=False`.
- **Stateful client.** `supports_stateful_client=False`; deferred to a later phase.
- **Agent migrations.** Per-agent switchover to Gemini is Phase C (separate PRs).

## 3. SDK Choice

The `google-genai` SDK (>= 1.0) unifies access to both Google AI Studio and Vertex AI:

| Auth mode | SDK constructor | API endpoint |
|---|---|---|
| API key | `genai.Client(api_key="...")` | Generative Language API (AI Studio) |
| ADC | `genai.Client(vertexai=True, project="...", location="...")` | Vertex AI |

This avoids maintaining two separate SDKs (`google-generativeai` vs `google-cloud-aiplatform`).

## 4. Architecture

### 4.1 Dual-backend pattern (mirrors OpenAI)

```
GeminiProvider
├── __init__(auth) → route by cred.kind
│   ├── cred.kind == "api_key"    → _DirectAPIBackend(cred)
│   └── cred.kind == "oauth2_adc" → _VertexAIBackend(cred)
├── query()   → delegate to self._backend.query()
├── client()  → raises UnsupportedCapabilityError
└── _translate_* hooks (shared across backends)
```

### 4.2 Capabilities

```python
# Both backends share the same capabilities in Phase B
_GEMINI_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=False,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)
```

### 4.3 Auth strategies

```python
class GeminiProvider(BaseProvider):
    supported_auth = (OAuth2ADC, ApiKey)
```

| Strategy | Credential kind | Source | Setup |
|---|---|---|---|
| `ApiKey` | `api_key` | `GEMINI_API_KEY` env var | Get key from AI Studio |
| `OAuth2ADC` | `oauth2_adc` | Application Default Credentials | `gcloud auth application-default login` |

### 4.4 OAuth2ADC strategy (new)

```python
@AuthRegistry.register("oauth2_adc")
class OAuth2ADC(AuthStrategy):
    kind: ClassVar[str] = "oauth2_adc"

    def __init__(self, *, project_id: str | None = None) -> None:
        self._project_id = project_id

    def resolve(self) -> Credential:
        return Credential(
            kind="oauth2_adc",
            payload={"project_id": self._project_id, "source": "adc"},
        )
```

The strategy is a pure value holder. The `google-genai` SDK handles actual ADC resolution internally when `vertexai=True`.

## 5. Translation hooks

### 5.1 `_translate_system_prompt`

| SystemPrompt subtype | Behavior |
|---|---|
| `TextSystemPrompt` | Pass `text` directly as `system_instruction` |
| `SkillReference` | Read file, pass content as `system_instruction` |
| `PresetSystemPrompt` | Raise `UnsupportedCapabilityError` (`supports_system_prompt_file=False`) |

### 5.2 `_translate_tools`

Map `ToolPolicy.allowed` to `allowed_tools` list. Custom `ToolSpec` maps to `genai.types.FunctionDeclaration`.

### 5.3 `_translate_mcp`

Raise `UnsupportedCapabilityError("gemini", "mcp")` if any servers are passed.

## 6. Backend details

### 6.1 `_DirectAPIBackend` (API key)

```python
class _DirectAPIBackend(_Backend):
    def __init__(self, cred: Credential) -> None:
        from google import genai
        self._client = genai.Client(api_key=cred.payload["api_key"])

    async def query(self, prompt, options, provider):
        sp_text = provider._translate_system_prompt(options.system_prompt)
        config = {"system_instruction": sp_text}
        if options.output_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = options.output_schema

        response = self._client.models.generate_content_stream(
            model=options.model, contents=prompt, config=config,
        )
        buffer = []
        for chunk in response:
            text = chunk.text or ""
            buffer.append(text)
            yield Message(text=text, is_final=False, raw=chunk)
        yield Message(text="".join(buffer), is_final=True, raw=None)
```

### 6.2 `_VertexAIBackend` (ADC)

```python
class _VertexAIBackend(_Backend):
    def __init__(self, cred: Credential) -> None:
        from google import genai
        extras = {}  # populated from ProviderOptions.extras["gemini"]
        self._project = cred.payload.get("project_id")
        self._location = extras.get("location", "us-central1")
        self._client = genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
        )
```

`project_id` comes from:
1. `OAuth2ADC(project_id=...)` constructor (set by `GeminiConfig.project_id` in settings)
2. `ProviderOptions.extras["gemini"]["project_id"]` (per-call override)
3. ADC environment default (if both are None)

## 7. Auth factory extension

```python
# In resolve_auth():
if provider_name == "gemini":
    if auth_kind == "api_key":
        key = creds.gemini_api_key
        if key is None:
            raise AuthResolutionError("Gemini api_key requires GEMINI_API_KEY.")
        return ApiKey(api_key=key.get_secret_value())
    if auth_kind == "oauth2_adc":
        from llm_providers.auth.oauth2_adc import OAuth2ADC
        return OAuth2ADC()
```

## 8. Packaging

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "google-genai>=1.0",
]
```

`google-genai` pulls `google-auth` transitively, so no explicit `google-auth` dependency needed.

## 9. Testing strategy

### 9.1 Conformance suite

Add `"gemini"` to `test_conformance.py` parametrize — all Liskov contract assertions run automatically.

### 9.2 Per-provider tests (`test_gemini.py`)

Same pattern as `test_openai.py`: isolate registration, stub the SDK, test backend routing, translation hooks, and error wrapping.

### 9.3 Auth strategy tests (`test_oauth2_adc.py`)

Test `resolve()` → `Credential(kind="oauth2_adc")`, project_id propagation.

### 9.4 Live smoke test (opt-in)

`@pytest.mark.live_gemini` — real API call with operator credentials. Manual-only; CI never runs it.

## 10. Operator env-var surface (new)

| Env var | Purpose |
|---|---|
| `GEMINI_API_KEY` | API key for Google AI Studio |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to SA JSON for ADC (existing GCP convention) |
| `HSB_RUNTIME_<AGENT>=gemini` | Flip any agent to Gemini |
| `HSB_AUTH_ALLOW_API_KEY_<AGENT>=1` | Enable API key auth for specific agent |
