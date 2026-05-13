# Gemini Provider — Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `src/llm_providers/providers/gemini.py` with two internal backends (_DirectAPIBackend for API key, _VertexAIBackend for ADC), register it in the provider registry, extend the auth factory, and pass the conformance suite.

**Architecture:** Follows the dual-backend pattern established by `OpenAIProvider` in Phase A. Single `GeminiProvider` class with backend selection by `cred.kind`. Uses the unified `google-genai` SDK (>= 1.0) for both AI Studio (API key) and Vertex AI (ADC) access.

**Tech Stack:** Python 3.12, `google-genai>=1.0`, `google-auth>=2.0`, `pytest` + `pytest-asyncio`, hatchling.

**Spec:** `docs/superpowers/specs/2026-05-13-gemini-provider-design.md`

**Depends on:** Phase A (`docs/superpowers/plans/2026-05-11-multi-provider-module.md`) — completed.

**Out of scope:**
- OAuth2 CLI token for Gemini (no official gemini-cli yet)
- Service account JSON strategy (future)
- MCP support (Gemini does not support MCP natively)
- Stateful client (deferred)
- Migrating agents to use Gemini (Phase C, separate PRs)

---

## File Structure

### Created

| File | Responsibility |
|---|---|
| `src/llm_providers/auth/oauth2_adc.py` | `OAuth2ADC` auth strategy — Google Application Default Credentials. |
| `src/llm_providers/providers/gemini.py` | `@register("gemini")` GeminiProvider with `_DirectAPIBackend` + `_VertexAIBackend`. |
| `tests/llm_providers/auth/test_oauth2_adc.py` | OAuth2ADC strategy tests. |
| `tests/llm_providers/providers/test_gemini.py` | GeminiProvider dual-backend routing + translation hooks (mocked SDK). |

### Modified

| File | Change |
|---|---|
| `src/llm_providers/auth/__init__.py` | Add `OAuth2ADC` import + `__all__` entry. |
| `src/llm_providers/auth/factory.py` | Add `gemini` branch (api_key + oauth2_adc). |
| `src/llm_providers/providers/__init__.py` | Add side-effect `gemini` import. |
| `src/llm_providers/__init__.py` | Add `OAuth2ADC` to public surface. |
| `src/settings/credentials.py` | Add `gemini_api_key: SecretStr \| None` field. |
| `pyproject.toml` | Add `google-genai>=1.0` to dependencies. |
| `.env.example` | Document `GEMINI_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS`. |
| `tests/llm_providers/test_conformance.py` | Add `"gemini"` to parametrize + registry assertion. |

---

## Task 1: OAuth2ADC Auth Strategy

**Files:** Create `oauth2_adc.py`, modify `auth/__init__.py`, tests.

- [ ] **Step 1: Write failing test** `tests/llm_providers/auth/test_oauth2_adc.py`

```python
"""OAuth2ADC strategy tests."""
from llm_providers.auth.oauth2_adc import OAuth2ADC


def test_resolve_returns_adc_credential():
    s = OAuth2ADC(project_id="my-project")
    cred = s.resolve()
    assert cred.kind == "oauth2_adc"
    assert cred.payload["project_id"] == "my-project"


def test_project_id_defaults_to_none():
    s = OAuth2ADC()
    cred = s.resolve()
    assert cred.payload["project_id"] is None


def test_kind_classvar():
    assert OAuth2ADC.kind == "oauth2_adc"
```

- [ ] **Step 2: Run test — expect ModuleNotFoundError**
- [ ] **Step 3: Implement `src/llm_providers/auth/oauth2_adc.py`**

```python
"""OAuth2ADC auth strategy — Google Application Default Credentials.

Uses google.auth.default() to resolve credentials from the environment.
Build via the auth factory which maps (gemini, oauth2_adc) → ADC.
"""
from __future__ import annotations
from typing import ClassVar
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.registry import AuthRegistry


@AuthRegistry.register("oauth2_adc")
class OAuth2ADC(AuthStrategy):
    """Google ADC credential holder."""
    kind: ClassVar[str] = "oauth2_adc"

    def __init__(self, *, project_id: str | None = None) -> None:
        self._project_id = project_id

    def resolve(self) -> Credential:
        return Credential(
            kind="oauth2_adc",
            payload={"project_id": self._project_id, "source": "adc"},
        )
```

- [ ] **Step 4: Add import to `auth/__init__.py`**
- [ ] **Step 5: Run tests — expect 3 passed**
- [ ] **Step 6: Lint + commit** `feat(llm_providers): OAuth2ADC auth strategy`

---

## Task 2: Auth Factory + Credentials Settings

**Files:** Modify `factory.py`, `credentials.py`.

- [ ] **Step 1: Add `gemini_api_key` to `CredentialsSettings`**

```python
gemini_api_key: SecretStr | None = Field(
    default=None,
    validation_alias="GEMINI_API_KEY",
)
```

- [ ] **Step 2: Add gemini branch to `resolve_auth`**

```python
if provider_name == "gemini":
    if auth_kind == "api_key":
        key = creds.gemini_api_key
        if key is None:
            raise AuthResolutionError(
                "Gemini api_key auth requires GEMINI_API_KEY to be set."
            )
        return ApiKey(api_key=key.get_secret_value())
    if auth_kind == "oauth2_adc":
        from llm_providers.auth.oauth2_adc import OAuth2ADC
        return OAuth2ADC()
```

- [ ] **Step 3: Update factory docstring table**
- [ ] **Step 4: Run existing auth tests + new settings tests**
- [ ] **Step 5: Lint + commit** `feat(llm_providers): gemini auth resolution in factory`

---

## Task 3: GeminiProvider Implementation

**Files:** Create `providers/gemini.py`.

- [ ] **Step 1: Write failing test** `tests/llm_providers/providers/test_gemini.py`

| # | Test | Description |
|---|------|-------------|
| 1 | `test_direct_backend_selected_for_api_key` | API key → `_DirectAPIBackend` |
| 2 | `test_vertex_backend_selected_for_adc` | ADC → `_VertexAIBackend` |
| 3 | `test_supported_auth` | `OAuth2ADC` and `ApiKey` present |
| 4 | `test_direct_query_streams_messages` | Smoke test streaming with fake SDK |
| 5 | `test_translate_system_prompt_text` | TextSystemPrompt → string |
| 6 | `test_translate_system_prompt_skill` | SkillReference → file content |
| 7 | `test_translate_system_prompt_preset_raises` | PresetSystemPrompt → UnsupportedCapabilityError |
| 8 | `test_mcp_raises_unsupported` | MCP servers → UnsupportedCapabilityError |
| 9 | `test_credential_mismatch_raises` | Unknown cred kind → CredentialMismatch |

- [ ] **Step 2: Run test — expect failure**
- [ ] **Step 3: Implement `gemini.py`** following OpenAI dual-backend pattern
  - `_DirectAPIBackend`: `genai.Client(api_key=...)` — AI Studio
  - `_VertexAIBackend`: `genai.Client(vertexai=True, project=..., location=...)` — Vertex AI
  - Both use `generate_content_stream()` for streaming
  - `project_id` and `location` come from `ProviderOptions.extras["gemini"]`
- [ ] **Step 4: Run tests — expect all passed**
- [ ] **Step 5: Lint + commit** `feat(llm_providers): GeminiProvider with dual backends`

---

## Task 4: Wiring + Conformance

**Files:** Modify `providers/__init__.py`, `llm_providers/__init__.py`, `pyproject.toml`, `.env.example`, `test_conformance.py`.

- [ ] **Step 1: Add side-effect import** in `providers/__init__.py`
- [ ] **Step 2: Add `OAuth2ADC` to `llm_providers/__init__.py`** public surface
- [ ] **Step 3: Add `google-genai>=1.0` to `pyproject.toml`** dependencies
- [ ] **Step 4: Document env vars** in `.env.example`
- [ ] **Step 5: Update `test_conformance.py`** — add `"gemini"` to parametrize
- [ ] **Step 6: Run `uv sync`**
- [ ] **Step 7: Run full test suite** `uv run pytest tests/llm_providers/ -v`
- [ ] **Step 8: Lint + commit** `feat(llm_providers): register Gemini provider + conformance`

---

## Verification Plan

### Automated Tests

```bash
uv run ruff check src/ tests/
uv run pytest tests/llm_providers/ -v --tb=short
uv run pytest tests/unit/settings/ -v --tb=short
```

### Manual Verification

#### API Key (AI Studio)

1. Get an API key at https://aistudio.google.com/apikey
2. Set it: `export GEMINI_API_KEY="AIza..."`
3. Run live smoke test:

```bash
uv run pytest tests/llm_providers/ -m live_gemini -v
```

4. Verify: streaming response ends with `is_final=True`

#### OAuth2 ADC (Vertex AI)

1. Authenticate via gcloud: `gcloud auth application-default login`
2. Set project: `export GOOGLE_CLOUD_PROJECT="my-project-id"`
3. Run live smoke test with ADC:

```bash
HSB_RUNTIME_BACKLOG=gemini uv run pytest tests/llm_providers/ -m live_gemini -v
```

4. Verify: response routes through Vertex AI endpoint (not AI Studio)

---

## Usage Guide — How to use Gemini in practice

### Option 1: API Key (simplest — local development)

**Setup:**

```bash
# 1. Get key at https://aistudio.google.com/apikey
# 2. Add to .env
echo 'GEMINI_API_KEY=AIzaSy...' >> .env
```

**Programmatic usage (inside an agent):**

```python
from llm_providers import ProviderRegistry
from llm_providers.auth.factory import resolve_auth
from llm_providers.prompt import TextSystemPrompt
from llm_providers.protocol import ProviderOptions
from llm_providers.tools import ToolPolicy

# Build the provider
auth = resolve_auth("gemini", "api_key")
provider = ProviderRegistry.build("gemini", auth=auth)

# Make a query
options = ProviderOptions(
    system_prompt=TextSystemPrompt(text="You are a helpful assistant."),
    model="gemini-2.5-flash",
    max_turns=1,
    tool_policy=ToolPolicy(),
)

async for msg in provider.query("Explain async/await in Python", options):
    if msg.is_final:
        print(msg.text)
```

**Usage via runtime (agent flip):**

```bash
# Any agent can use Gemini by switching the env var:
export HSB_RUNTIME_BACKLOG=gemini
export HSB_AUTH_ALLOW_API_KEY_BACKLOG=1  # required when using API key (G1 policy)

# Run normally — the backlog agent now uses Gemini
uv run python run_loop.py
```

### Option 2: OAuth2 ADC (production — Vertex AI)

**Setup:**

```bash
# 1. Authenticate with Google Cloud
gcloud auth application-default login

# 2. Set project
export GOOGLE_CLOUD_PROJECT="my-project-id"
```

**Programmatic usage:**

```python
from llm_providers import ProviderRegistry
from llm_providers.auth.factory import resolve_auth

# ADC resolves automatically via gcloud / GOOGLE_APPLICATION_CREDENTIALS
auth = resolve_auth("gemini", "oauth2_adc")
provider = ProviderRegistry.build("gemini", auth=auth)

# Extras for Vertex AI (project + location)
options = ProviderOptions(
    system_prompt=TextSystemPrompt(text="..."),
    model="gemini-2.5-pro",
    max_turns=5,
    tool_policy=ToolPolicy(),
    extras={"gemini": {"project_id": "my-project", "location": "us-east4"}},
)
```

**Usage via runtime:**

```bash
# ADC is the G1 default (OAuth2-only) — no escape hatch needed
export HSB_RUNTIME_BACKLOG=gemini
# project_id comes from GeminiConfig in settings
uv run python run_loop.py
```

### Option 3: Via ProviderSettings (declarative configuration)

```python
from settings.provider import ProviderSettings, ProviderName, OAuth2ADCAuth, GeminiConfig

# Gemini with API key
settings = ProviderSettings(
    name=ProviderName.gemini,
    model="gemini-2.5-flash",
    auth=ApiKeyAuth(key="AIzaSy..."),
)

# Gemini with ADC (Vertex AI)
settings = ProviderSettings(
    name=ProviderName.gemini,
    model="gemini-2.5-pro",
    auth=OAuth2ADCAuth(),
    gemini=GeminiConfig(project_id="my-project", location="us-central1"),
)
```

### Available models

| Model ID | Recommended use | Context |
|---|---|---|
| `gemini-3.1-pro` | Flagship reasoning, complex agentic tasks | 2M tokens |
| `gemini-3.1-flash` | Best speed/quality balance, latest generation | 2M tokens |
| `gemini-2.5-pro` | High quality reasoning, complex tasks | 1M tokens |
| `gemini-2.5-flash` | Speed/quality balance | 1M tokens |
| `gemini-2.5-flash-lite` | Maximum speed, minimum cost | 1M tokens |
| `gemini-2.0-flash` | Legacy, backward compatibility | 1M tokens |

## References

- Phase A plan: `docs/superpowers/plans/2026-05-11-multi-provider-module.md`
- Phase A spec: `docs/superpowers/specs/2026-05-11-multi-provider-module-design.md`
- OpenAI dual-backend reference: `src/llm_providers/providers/openai.py`
- Auth factory: `src/llm_providers/auth/factory.py`
- Module README: `src/llm_providers/README.md`
