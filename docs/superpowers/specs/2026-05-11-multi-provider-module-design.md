# Multi-Provider LLM Module — Design

**Date:** 2026-05-11
**Status:** Spec — pending implementation plan
**Branch:** `design/multi-provider-module`
**Supersedes (in spirit):** the runtime split in `2026-05-09-codex-oauth-alt-runtime-design.md` — that spec's `Runtime` Protocol becomes a thin consumer of this library; its `ClaudeRuntime`/`CodexRuntime` are absorbed as `ClaudeProvider`/`OpenAIProvider`.

---

## 1. Goal

Introduce a decoupled, extensible LLM provider library that lets the project add new LLM execution backends (Claude, OpenAI/Codex, Gemini, future) without modifying existing code. The library follows Liskov substitutability: every provider satisfies the same contract; vendor specifics are reachable through capability flags and a namespaced `extras` channel. Auth is modeled as a first-class Strategy: OAuth2 is the preferred mechanism for each provider, with optional API-key fallback. The project (`hsb.*`) consumes the library and layers its own policy (G1 OAuth2-only by default, per-agent escape hatches, G2/G3/G5 guards) on top.

## 2. Non-goals

- **Replacing third-party agent frameworks.** The library wraps each vendor's *official* SDK (`claude-agent-sdk`, `openai-codex-sdk` + `openai`, `google-genai`). It is not LangChain/CrewAI/AutoGen.
- **Built-in mid-run provider switching.** The library does not orchestrate switching providers inside a single `query()` stream or stateful `client()` session — once a provider instance is constructed and a call is in flight, that call completes on that provider. This is not an architectural prohibition: a consumer can perfectly well build its own switching layer on top by holding two `BaseProvider` instances and routing between them at message boundaries (e.g., retry on a different provider after failure, A/B comparison, hot-swap on quota exhaustion). The library exposes the building blocks (registry, capability flags, error model) but ships no opinionated switcher.
- **Built-in fallback chain between providers.** When a chosen provider fails (network, quota, auth), the library raises a `ProviderRuntimeError` with the original SDK exception as `__cause__`. The initial release does not ship a built-in fallback chain that automatically retries the same call on a different provider. This is not an architectural prohibition: the registry, capability flags, and error model are designed so a consumer (or a later iteration of the library itself) can layer a fallback orchestrator on top — choosing per-call which providers to try, in what order, on which error classes, with what observability. It is intentionally a future-plan capability rather than an initial scope item, because the right fallback policy depends on real-world failure modes and downstream observability requirements that we have not yet measured.
- **Cross-provider text equality.** Output text varies across providers; Pydantic schema parity is the contract, not text parity.
- **Migrating every direct-SDK agent in one PR.** Per-agent migrations follow the existing recipe in `agents/AGENT-CONTRACTS.md`; they are independent, parallelizable, follow-up PRs.
- **WIO (Work Item Orchestrator) provider flippability.** WIO stays on Claude via `ClaudeSDKClient`. Hard-blocked at the consumer layer; tracked separately.

## 3. Context

The project's `AGENTS.md` mandates "tool-agnostic agent design (no hard dependency on Claude Code vs. Codex)." Today `hsb.runtime` implements that for two backends via `ClaudeRuntime` and `CodexRuntime`, selected via `HSB_RUNTIME_<AGENT>` env var. The selection lives in a `resolve_runtime()` function with an `if/elif/else` chain — closed for direct extension. Adding Gemini today would require editing `resolve_runtime`, adding a new `GeminiRuntime` next to the existing two, and replicating the G1 OAuth2 guard logic per-runtime.

This spec replaces the closed dispatch with a registry-driven module that is open for extension (new providers register themselves) and closed for modification (no existing file is edited to add a provider). It also softens the project's "OAuth2 only" hard rule into a configurable consumer-side policy, since the user requirements now allow API keys as an alternative when explicitly opted in per agent.

## 4. Architecture

A new top-level package `src/llm_providers/` lives independently of `hsb.*`. It has zero imports from `hsb` (enforced by a structural test) and could be extracted to its own PyPI package later without code changes. `hsb.runtime` becomes a thin adapter that consumes the library and layers project-specific policy on top.

```
src/
├── llm_providers/                   ← decoupled library (no hsb imports)
│   ├── __init__.py                  ← public surface; side-effect imports trigger registration
│   ├── README.md                    ← contributor onboarding (§6 below)
│   ├── protocol.py                  ← Message, Capabilities, ProviderOptions, PermissionMode
│   ├── base.py                      ← BaseProvider(ABC)
│   ├── registry.py                  ← ProviderRegistry, AuthRegistry (decorator pattern)
│   ├── errors.py                    ← LLMProvidersError hierarchy
│   ├── prompt.py                    ← TextSystemPrompt, SkillReference, PresetSystemPrompt
│   ├── tools.py                     ← ToolSpec, McpServerSpec
│   ├── auth/
│   │   ├── __init__.py              ← side-effect imports for strategy registration
│   │   ├── base.py                  ← AuthStrategy(ABC), Credential
│   │   ├── api_key.py               ← ApiKey
│   │   ├── oauth2_cli.py            ← OAuth2CliToken (claude/codex/gemini-cli style)
│   │   ├── oauth2_adc.py            ← OAuth2Adc (Google ADC)
│   │   └── oauth2_service_account.py← OAuth2ServiceAccount (Google SA JSON)
│   └── providers/
│       ├── __init__.py              ← side-effect imports for provider registration
│       ├── claude.py                ← @register("claude") ClaudeProvider
│       ├── openai.py                ← @register("openai") OpenAIProvider (Codex CLI + raw API backends)
│       └── gemini.py                ← @register("gemini") GeminiProvider
│
└── hsb/
    └── runtime/                     ← thin consumer adapter (G1, env-var routing, project policy)
        ├── protocol.py              ← AgentOptions/Message (wrappers/aliases over library types)
        ├── policy.py                ← G1 OAuth2-only allowlist; per-agent escape hatch
        ├── resolver.py              ← resolve_runtime() → HsbProviderHandle
        ├── handle.py                ← HsbProviderHandle (G3 backstop)
        └── compat.py                ← ClaudeRuntime / CodexRuntime deprecation shims
```

**Invariants:**

1. **Library is policy-free.** It exposes both OAuth2 and API-key strategies as equal. The consumer (`hsb.runtime.policy`) imposes "OAuth2 only" as a project-level rule.
2. **No circular knowledge.** Providers never import `hsb.*`. Enforced by a CI-time AST check in `tests/llm_providers/test_conformance.py`.
3. **Adding a provider is one file** plus one line in `providers/__init__.py`. No edits to `registry.py`, `base.py`, `protocol.py`, or any other provider.
4. **Adding an auth strategy is one file** plus one line in `auth/__init__.py`.
5. **Lazy SDK imports.** Vendor SDKs are imported inside `__init__`/method bodies, not at module top. Operators install only the extras they need.

## 5. Core abstractions

### 5.1 `ProviderOptions` (frozen dataclass)

```python
@dataclass(frozen=True)
class ProviderOptions:
    system_prompt: SystemPrompt              # sum type, not raw str (see 5.4)
    model: str
    max_turns: int
    tool_policy: ToolPolicy                  # see 5.5
    mcp_servers: tuple[McpServerSpec, ...] = ()
    permission_mode: PermissionMode = "default"
    output_schema: dict | None = None
    cwd: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)
```

`extras` is a vendor-namespaced escape hatch: `extras={"claude": {"hooks": [...]}}`. Each provider reads `extras.get(self.name, {})`; all others ignore it. Liskov holds — every provider accepts the same `ProviderOptions`; vendor specifics are opt-in and explicit. Each provider documents its recognized `extras` keys in its module docstring and in `README.md` §3 "Adding a new provider" — unknown keys are ignored rather than rejected, so a caller can pass a multi-vendor `extras` dict without breaking on providers that don't know one of the namespaces.

### 5.2 `Capabilities` (frozen dataclass)

```python
@dataclass(frozen=True)
class Capabilities:
    supports_mcp: bool
    supports_native_tools: bool
    supports_hooks: bool
    supports_stateful_client: bool
    supports_output_schema: bool
    supports_system_prompt_file: bool
    supports_streaming: bool
    max_context_tokens: int | None = None
```

Each provider declares `capabilities: ClassVar[Capabilities]`. `BaseProvider.require_capability(name)` raises `UnsupportedCapabilityError(provider=..., capability=...)` when a feature is requested that the provider does not support. Callers can query `provider.capabilities.supports_mcp` before constructing options.

### 5.3 `BaseProvider` (ABC)

```python
class BaseProvider(ABC):
    name: ClassVar[str]
    capabilities: ClassVar[Capabilities]
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]]   # ordered, preferred first

    def __init__(self, auth: AuthStrategy) -> None:
        self._auth = self._validate_auth(auth)

    @classmethod
    def _validate_auth(cls, auth: AuthStrategy) -> AuthStrategy:
        if not isinstance(auth, cls.supported_auth):
            raise UnsupportedAuthError(
                provider=cls.name,
                got=type(auth).__name__,
                accepted=[a.__name__ for a in cls.supported_auth],
            )
        return auth

    @abstractmethod
    async def query(self, prompt: str, options: ProviderOptions) -> AsyncIterator[Message]: ...

    @abstractmethod
    def client(self, options: ProviderOptions) -> StatefulClient: ...

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any: ...
    def _translate_tools(self, policy: ToolPolicy) -> Any: ...
    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> Any: ...
```

Template Method pattern — shared validation in the base, vendor-specific translation in the overrides.

### 5.4 `SystemPrompt` sum type (skills support)

```python
class SystemPrompt(ABC): ...

@dataclass(frozen=True)
class TextSystemPrompt(SystemPrompt):
    text: str

@dataclass(frozen=True)
class SkillReference(SystemPrompt):
    """A markdown skill file. Translated per provider:
       - Claude:  SystemPromptFile(path=...) (native)
       - OpenAI:  read+inline as <system>...</system> (Codex) or messages[0] (raw API)
       - Gemini:  read+pass as config.system_instruction
    """
    path: Path
    locator: str | None = None               # e.g. ".claude/skills/uat-validation/SKILL.md"

@dataclass(frozen=True)
class PresetSystemPrompt(SystemPrompt):
    preset_id: str                           # only valid if supports_system_prompt_file
```

This is the **skills handling**: skills are first-class. The consumer reads `.claude/skills/<name>/SKILL.md` once (today's `load_skill(path)` pattern) and passes either the resulting `str` (wrapped in `TextSystemPrompt`) or a `SkillReference(path=...)` directly. The provider's `_translate_system_prompt` decides what to do per its capabilities.

### 5.5 `ToolPolicy` + `McpServerSpec`

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict                       # JSON Schema
    handler: Callable[..., Awaitable[Any]] | None = None

@dataclass(frozen=True)
class ToolPolicy:
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    custom: tuple[ToolSpec, ...] = ()

@dataclass(frozen=True)
class McpServerSpec:
    name: str
    transport: Literal["stdio", "http"]
    command: tuple[str, ...] | None = None   # stdio
    url: str | None = None                   # http
    env: Mapping[str, str] = field(default_factory=dict)
```

## 6. Authentication

### 6.1 `AuthStrategy` base (Strategy pattern)

```python
@dataclass(frozen=True)
class Credential:
    kind: Literal["api_key", "oauth2_cli_token", "oauth2_adc", "oauth2_service_account"]
    payload: Mapping[str, Any]

class AuthStrategy(ABC):
    kind: ClassVar[str]

    @abstractmethod
    def detect(self) -> bool: ...

    @abstractmethod
    def resolve(self) -> Credential: ...

    @classmethod
    @abstractmethod
    def default(cls) -> "AuthStrategy": ...   # zero-arg conventional constructor
```

### 6.2 Concrete strategies

| Class | `kind` | What it does |
|---|---|---|
| `ApiKey` | `"api_key"` | Holds a literal key from env var. Constructed with `env_var=`. |
| `OAuth2CliToken` | `"oauth2_cli_token"` | Reads token written by vendor CLI (`CLAUDE_CODE_OAUTH_TOKEN`, `~/.codex/auth.json`, `~/.gemini/oauth.json`). |
| `OAuth2Adc` | `"oauth2_adc"` | Google Application Default Credentials via `google.auth.default()`. |
| `OAuth2ServiceAccount` | `"oauth2_service_account"` | Service-account JSON via `google.oauth2.service_account.Credentials`. |

### 6.3 Provider-declared preferred order

```python
class ClaudeProvider(BaseProvider):
    supported_auth = (OAuth2CliToken, ApiKey)

class OpenAIProvider(BaseProvider):
    supported_auth = (OAuth2CliToken, ApiKey)

class GeminiProvider(BaseProvider):
    supported_auth = (OAuth2CliToken, OAuth2Adc, OAuth2ServiceAccount, ApiKey)
```

### 6.4 Gemini OAuth — state of the art

| Strategy resolved | SDK used | API endpoint | Operator setup |
|---|---|---|---|
| `OAuth2CliToken(path=<configurable>)` | `google-genai` with bearer | Generative Language API | Operator writes a Google OAuth2 token file (e.g. via gemini-cli when available, or a custom flow). Default path is configurable; the strategy makes no assumption about which CLI populated it. |
| `OAuth2Adc` | `google-genai` with ADC | Generative Language or Vertex (via `extras["gemini"]["use_vertex"]`) | `gcloud auth application-default login` |
| `OAuth2ServiceAccount` | `google-genai` via `vertexai` | Vertex AI | `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json` |
| `ApiKey` (`GEMINI_API_KEY` / `GOOGLE_API_KEY`) | `google-genai` with api_key | AI Studio | n/a |

### 6.5 Resolution

```python
def auto_resolve_auth(
    provider_name: str,
    *,
    accepted_kinds: Iterable[str] | None = None,
) -> AuthStrategy:
    """Walk provider.supported_auth in declared order. Return the first
       strategy that (1) has a kind in accepted_kinds if provided, (2)
       constructs via .default(), and (3) detect() returns True. Raise
       AuthResolutionError listing every strategy tried and why it was
       skipped if exhausted."""
```

`accepted_kinds` is the consumer-side policy filter. `hsb.runtime.policy.allowed_auth_kinds()` calls it with the OAuth2-only set by default; the per-agent escape hatch (`HSB_AUTH_ALLOW_API_KEY_<AGENT>=1`) widens it to include `"api_key"`.

## 7. Per-provider classes

### 7.1 `ClaudeProvider`

```python
@ProviderRegistry.register("claude")
class ClaudeProvider(BaseProvider):
    name = "claude"
    capabilities = Capabilities(
        supports_mcp=True,
        supports_native_tools=True,
        supports_hooks=True,
        supports_stateful_client=True,
        supports_output_schema=True,
        supports_system_prompt_file=True,
        supports_streaming=True,
    )
    supported_auth = (OAuth2CliToken, ApiKey)
```

- Translates `SkillReference` → `SystemPromptFile(path=...)`.
- `_translate_tools` → `allowed_tools=list(policy.allowed)`. Custom `ToolSpec`s map to `@tool`-decorated MCP server (in-process).
- `_translate_mcp` → translates `McpServerSpec` tuple to claude-agent-sdk's `mcp_servers` dict.
- `extras["claude"]["hooks"]` is the escape hatch for `HookMatcher`.

### 7.2 `OpenAIProvider` (dual backend)

```python
@ProviderRegistry.register("openai")
class OpenAIProvider(BaseProvider):
    name = "openai"
    supported_auth = (OAuth2CliToken, ApiKey)

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        cred = self._auth.resolve()
        if cred.kind == "oauth2_cli_token":
            self._backend = _CodexBackend(cred)        # openai-codex-sdk
        elif cred.kind == "api_key":
            self._backend = _RawOpenAIBackend(cred)    # openai
        else:
            raise CredentialMismatch(...)

    @property
    def capabilities(self) -> Capabilities:
        return self._backend.capabilities              # backend-dependent
```

Codex CLI OAuth (operator's ChatGPT subscription) and `OPENAI_API_KEY` (api.openai.com) are both legitimately "OpenAI". The provider routes internally based on credential kind. Backends share `_translate_*` hooks; capabilities are backend-dependent (e.g. `supports_mcp=True` only on Codex backend).

> Note on Liskov: `BaseProvider.capabilities` is declared as `ClassVar[Capabilities]`. Most providers satisfy this with a literal class attribute. Providers with backend-dependent capabilities may override `capabilities` as an instance `@property` returning a `Capabilities` object — the conformance test in §13.1 asserts on `provider.capabilities` (an instance access) rather than on `type(provider).capabilities`, so both forms pass.

### 7.3 `GeminiProvider`

```python
@ProviderRegistry.register("gemini")
class GeminiProvider(BaseProvider):
    name = "gemini"
    capabilities = Capabilities(
        supports_mcp=False,
        supports_native_tools=True,
        supports_hooks=False,
        supports_stateful_client=True,
        supports_output_schema=True,
        supports_system_prompt_file=False,
        supports_streaming=True,
    )
    supported_auth = (OAuth2CliToken, OAuth2Adc, OAuth2ServiceAccount, ApiKey)
```

- `_build_client` switches between `genai.Client(api_key=...)`, `genai.Client(vertexai=True, ...)`, and `genai.Client(credentials=...)` based on `cred.kind`.
- `SkillReference` → read file, pass as `config.system_instruction=<text>`.
- `_translate_tools` → maps each `ToolSpec` to `genai.types.Tool` with `function_declarations`.
- `_translate_mcp` → raises `UnsupportedCapabilityError("gemini", "mcp")` if `servers` non-empty.

## 8. Registry and resolution

### 8.1 `ProviderRegistry`

```python
class ProviderRegistry:
    _providers: ClassVar[dict[str, type[BaseProvider]]] = {}

    @classmethod
    def register(cls, name: str): ...           # decorator; rejects duplicates & name-mismatches

    @classmethod
    def get(cls, name: str) -> type[BaseProvider]: ...

    @classmethod
    def build(cls, name: str, *, auth: AuthStrategy) -> BaseProvider: ...

    @classmethod
    def build_auto(cls, name: str, *, accepted_kinds: Iterable[str] | None = None) -> BaseProvider: ...

    @classmethod
    def names(cls) -> tuple[str, ...]: ...
```

### 8.2 `AuthRegistry`

Symmetric shape, smaller surface. Used for introspection and validation in error messages.

### 8.3 Side-effect import structure

`src/llm_providers/providers/__init__.py`:

```python
"""Importing this package triggers provider registration as a side effect."""
from llm_providers.providers import claude   # noqa: F401
from llm_providers.providers import openai   # noqa: F401
from llm_providers.providers import gemini   # noqa: F401
```

`src/llm_providers/__init__.py` re-exports the public surface AND imports `llm_providers.providers` to trigger registration. Adding a new provider is one new file plus one line in `providers/__init__.py`.

### 8.4 What is closed for modification

| Action | Files edited |
|---|---|
| Add a new provider | 1 new file `providers/<name>.py` + 1 line in `providers/__init__.py` |
| Add a new auth strategy | 1 new file `auth/<kind>.py` + 1 line in `auth/__init__.py` |
| Change provider's auth ordering | Edit `supported_auth` tuple in that provider's file only |
| Add a new capability flag | Add field to `Capabilities` + each provider opts in (additive) |
| Tighten consumer policy (hsb) | Edit `hsb.runtime.policy` only |

## 9. Module README

`src/llm_providers/README.md` is the contributor onboarding doc. Sections:

1. What this library is (1 paragraph)
2. Mental model (3 layers: protocol / providers / consumers)
3. Adding a new provider (skeleton + worked example, ~80 lines)
4. Adding a new auth strategy (skeleton + worked example)
5. Capabilities — when to flip each flag (table)
6. Translation hooks contract (per-hook specification)
7. Error model (which exception to raise when)
8. Testing your provider (conformance suite + per-provider tests)
9. Do / Don't anti-patterns
10. PR-ready checklist (copy into PR description)

The two worked examples are the highest-leverage content: each is copy-pasteable, fits one screen, and shows the entire shape (`@register` decorator, class attributes, three translation hooks, side-effect import line).

## 10. Consumer adapter (`hsb.runtime`)

### 10.1 Layered shape

```
src/hsb/runtime/
├── protocol.py    ← AgentOptions = ProviderOptions (TypeAlias); Message re-exported from library;
│                    the existing Runtime Protocol class becomes a deprecation alias for BaseProvider
│                    so `isinstance(x, Runtime)` checks in legacy code keep working for one release.
├── policy.py      ← G1 OAuth2-only allowlist; configurable per-agent escape hatch
├── resolver.py    ← resolve_runtime() — env var routing, returns HsbProviderHandle
├── handle.py      ← HsbProviderHandle (G3 backstop)
└── compat.py      ← ClaudeRuntime / CodexRuntime deprecation shims
```

### 10.2 G1 as configurable consumer policy

```python
# src/hsb/runtime/policy.py
_DEFAULT_ALLOWED_AUTH_KINDS = frozenset({
    "oauth2_cli_token", "oauth2_adc", "oauth2_service_account",
})

def allowed_auth_kinds(agent_name: str) -> Iterable[str]:
    base = set(_DEFAULT_ALLOWED_AUTH_KINDS)
    if os.environ.get(f"HSB_AUTH_ALLOW_API_KEY_{agent_name.upper()}") == "1":
        base.add("api_key")
    return frozenset(base)
```

`assert_oauth2_only()` becomes a thin call into this allowlist. The function-entry semantics (not module-import-time) are preserved.

### 10.3 `resolve_runtime` is now a data-driven lookup

```python
_HARD_BLOCKED: dict[str, tuple[str, ...]] = {
    "wio": ("openai", "gemini"),     # WIO stays on Claude (stateful client)
}

def resolve_runtime(agent_name: str) -> HsbProviderHandle:
    env_var = f"HSB_RUNTIME_{agent_name.upper()}"
    provider_name = os.environ.get(env_var, "claude").strip().lower()
    if provider_name == "codex":
        warn("HSB_RUNTIME_<AGENT>=codex is deprecated; use =openai.", DeprecationWarning)
        provider_name = "openai"
    if provider_name in _HARD_BLOCKED.get(agent_name.lower(), ()):
        raise ValueError(...)
    provider = ProviderRegistry.build_auto(
        provider_name,
        accepted_kinds=allowed_auth_kinds(agent_name),
    )
    return HsbProviderHandle(provider=provider, agent_name=agent_name)
```

No `if claude / elif openai / elif gemini`. Adding Gemini is purely operational.

### 10.4 `HsbProviderHandle` carries G3

```python
@dataclass(frozen=True)
class HsbProviderHandle:
    provider: BaseProvider
    agent_name: str

    async def query(self, prompt, options):
        async for msg in self.provider.query(prompt, options):
            assert_no_task_dispatch(msg)     # G3 runtime backstop
            yield msg

    def client(self, options):
        return self.provider.client(options)
```

G3 is consumer policy — wraps every library message. G5 (Linear-write decorator) stays where it is on the LinearAgent methods; unchanged.

## 11. Consumer impact

### 11.1 Today's consumers

| Consumer | How it consumes today | Impact of Phase A PR |
|---|---|---|
| `backlog_agent.py` | `make_agent_options` + `resolve_runtime("backlog")` | **No code change.** Becomes the first agent that can flip to Gemini for free. |
| `uat_agent.py`, `risk_agent.py`, `linear_agent.py`, `git_agent.py`, `qa_agent.py`, `builder_agent.py`, `intelligence_agent.py` | `make_options` + direct `claude_agent_sdk.query(...)` | **No code change.** Still on direct-SDK path; `make_options` signature unchanged. |
| `work_item_orchestrator.py` | Stateful `ClaudeSDKClient` + `@tool` + hooks | **No code change.** Hard-blocked in `_HARD_BLOCKED`. |
| `main_orchestrator.py`, `global_orchestrator.py` | Pure Python, no SDK | **Untouched.** |
| `hooks.py` | `HookMatcher` (Claude-only) | **Untouched.** Library's `extras["claude"]["hooks"]` channel carries it. |
| `_sdk_options.py` | The chokepoint module | **Internal rewrite.** `assert_oauth2_only()` delegates to `policy.allowed_auth_kinds()`. `resolve_runtime()` becomes a 10-line wrapper. `make_options()` and `make_agent_options()` keep full signatures. |

### 11.2 Test consumers

`tests/runtime/test_claude_runtime.py`, `test_codex_runtime.py`, `test_codex_guards.py`, `test_make_options_branches.py`, `test_protocol.py`, `tests/integration/test_backlog_*` all continue to pass via the `compat.py` shims. **New tests** added under `tests/llm_providers/`: conformance suite, per-provider tests, auth strategy tests, registry tests.

### 11.3 Operator env-var surface

| Env var | Status |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Preserved — read by `OAuth2CliToken`. |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Blocked by G1 default. Allowed when `HSB_AUTH_ALLOW_API_KEY_<AGENT>=1`. |
| `~/.codex/auth.json` + `forced_login_method = "chatgpt"` | Preserved — verified by Codex backend init. |
| `HSB_RUNTIME_<AGENT>` | Preserved — value set widens to include `gemini`. `codex` is a deprecation alias for `openai`. |
| `CODEX_PATH_OVERRIDE`, `CODEX_HOME` | Preserved. |
| **New:** `HSB_AUTH_ALLOW_API_KEY_<AGENT>` | Per-agent G1 escape hatch. |
| **New:** `GOOGLE_APPLICATION_CREDENTIALS`, `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini auth strategies. |

### 11.4 Three-phase delivery

```
Phase A — Library extraction (this design's PR)
  - Add src/llm_providers/ with Claude + OpenAI providers.
  - Rewire hsb.runtime to consume the library; compat shims preserve old imports.
  - All existing tests pass; no agent code changes.
  - HSB_RUNTIME_<AGENT>=codex still works (alias with DeprecationWarning).

Phase B — Gemini provider (separate PR)
  - Add src/llm_providers/providers/gemini.py + Google auth strategies.
  - Add google-genai + google-auth to optional 'gemini' extra.
  - Conformance tests run automatically against the new provider.
  - Operational: HSB_RUNTIME_BACKLOG=gemini flips Backlog with no code change.

Phase C — Per-agent migrations (one PR per agent, parallelizable)
  - UAT, Risk, Linear, Git, QA, Builder, Intelligence each switch from
    direct SDK + make_options to runtime adapter + make_agent_options.
  - Follows existing recipe in agents/AGENT-CONTRACTS.md verbatim.
  - WIO stays on Claude (hard-blocked).
```

Phase A is the only PR with structural risk. Phases B and C are additive and isolated.

## 12. Error model

```python
class LLMProvidersError(Exception):                      # root
class ProviderNotFoundError(LLMProvidersError): ...      # unregistered name
class UnsupportedAuthError(LLMProvidersError): ...       # auth not in supported_auth
class UnsupportedCapabilityError(LLMProvidersError): ... # feature not exposed by provider
class AuthResolutionError(LLMProvidersError): ...        # auto_resolve_auth exhausted
class AuthDetectionFailed(LLMProvidersError): ...        # detect()=True but resolve() failed
class CredentialMismatch(LLMProvidersError): ...         # provider+credential drift
class TranslationError(LLMProvidersError): ...           # _translate_* produced invalid output
class ProviderRuntimeError(LLMProvidersError): ...       # wraps SDK exception as __cause__
```

Library does not raise generic `RuntimeError`/`ValueError` for library-domain failures. `ValueError` is reserved for "nonsensical value at public API boundary" (e.g. duplicate registration name).

## 13. Testing strategy

### 13.1 Conformance test suite — parametrized over registered providers

`tests/llm_providers/test_conformance.py` runs the same assertions against every registered provider with mocked SDKs. This is the load-bearing piece: it guarantees Liskov substitutability and catches drift when a fourth provider lands.

Assertions include:
- `capabilities` is a `Capabilities` frozen dataclass
- `supported_auth` is a non-empty tuple of `AuthStrategy` subclasses
- Passing unsupported auth raises `UnsupportedAuthError`
- `query()` yields `Message` objects with a final message where `is_final=True`
- Unsupported capabilities raise `UnsupportedCapabilityError` when exercised
- **Provider module does not import `hsb.*`** (AST-based assertion)
- `_translate_system_prompt` handles all three `SystemPrompt` subtypes

### 13.2 Per-provider, per-auth-strategy, consumer-side tests

- `tests/llm_providers/providers/test_<name>.py` — auth resolution paths, translation hook outputs, SDK error wrapping.
- `tests/llm_providers/auth/test_<kind>.py` — `detect()` true/false matrix, `resolve()` Credential shape, `default()` constructor.
- `tests/runtime/test_policy.py` — G1 allowlist + per-agent API-key escape hatch.
- `tests/runtime/test_resolver.py` — env-var routing, hard-blocks, `codex` → `openai` alias deprecation warning.
- `tests/runtime/test_handle.py` — G3 backstop fires on Task-tool message.

### 13.3 Live smoke tests (manual, opt-in)

Following the existing `@pytest.mark.live_codex` pattern: a new `@pytest.mark.live_gemini` marker for a real Gemini API smoke test against operator credentials. Manual-only; CI never runs them.

## 14. Packaging

### 14.1 In-repo (Phase A)

`pyproject.toml`:

```toml
[project.optional-dependencies]
gemini = ["google-genai>=1.0", "google-auth>=2.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/hsb", "src/llm_providers"]
```

`claude-agent-sdk` and `openai-codex-sdk` stay in main `dependencies` for now (the project requires both today). They move to optional extras after Phase C completes.

### 14.2 Extraction roadmap (out of scope; design enables it)

The "no imports from `hsb`" invariant from §4, enforced at CI time, makes future extraction to a standalone `llm-providers` PyPI package mechanical:
1. New repo `llm-providers/` containing only `src/llm_providers/` + its tests.
2. Its `pyproject.toml` declares optional extras `[claude]`, `[openai]`, `[gemini]`.
3. This project's `pyproject.toml` adds `"llm-providers[claude,openai]"` as a dependency, deletes `src/llm_providers/`.
4. `hsb.runtime` imports stay identical (`from llm_providers import …`).

### 14.3 Versioning

SemVer. Initial `0.1.0` for Phase A. Adding a provider or capability flag is a minor bump. Removing a provider, renaming a public class, or changing `ProviderOptions` field semantics is a major bump.

## 15. Out of scope (explicit)

- Stateful client port for WIO (tracked separately; `_HARD_BLOCKED` formalizes the gap).
- Replacing `make_options` / direct-SDK paths in UAT, Risk, Linear, Git, QA, Builder, Intelligence agents (Phase C, separate PRs).
- Adding any provider beyond Claude, OpenAI, Gemini in the initial spec — the registry pattern documents how, but the implementation ships these three only.
- Standalone PyPI extraction (designed for, but a follow-up project).
- A vendor-neutral hook abstraction. `HookMatcher` stays Claude-only via `extras["claude"]["hooks"]`.
- **Provider orchestration patterns** — built-in fallback chains, mid-run provider switching, A/B comparison harnesses, hot-swap-on-quota. The library exposes the primitives (registry, capability flags, structured error model) so a consumer (or a later iteration) can build any of these on top. Designing the right orchestrator requires real-world failure-mode data we don't yet have, so it is intentionally deferred rather than guessed at.
