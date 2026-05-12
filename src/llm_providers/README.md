# llm_providers — Multi-Provider LLM Library

Decoupled, OCP-compliant library for working with multiple LLM execution backends behind one Liskov-substitutable interface. Each provider is one file; adding a new one requires no edits to existing code.

## Mental model — three layers

1. **Protocol** (`protocol.py`, `prompt.py`, `tools.py`, `errors.py`) — vendor-neutral types every provider speaks. `ProviderOptions`, `Capabilities`, `Message`, `SystemPrompt`, `ToolPolicy`, `LLMProvidersError`.
2. **Providers + Auth** (`providers/`, `auth/`, `base.py`, `registry.py`) — `BaseProvider` ABC; per-vendor concrete classes; `AuthStrategy` ABC; per-mechanism concrete strategies; two decorator registries.
3. **Consumers** (anything outside this library) — call `ProviderRegistry.build_auto("claude", accepted_kinds=...)`, get a `BaseProvider`, use `await provider.query(prompt, options)`.

## Adding a new provider

### 3.1 Create the file

Pick a name (e.g. `mistral`) and create `src/llm_providers/providers/mistral.py`:

```python
from __future__ import annotations
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import UnsupportedCapabilityError
from llm_providers.prompt import (
    PresetSystemPrompt, SkillReference, SystemPrompt, TextSystemPrompt,
)
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


@ProviderRegistry.register("mistral")
class MistralProvider(BaseProvider):
    """MistralProvider — wraps mistral_sdk.

    Recognized ProviderOptions.extras["mistral"] keys: none.
    """
    name: ClassVar[str] = "mistral"
    capabilities: ClassVar[Capabilities] = Capabilities(
        supports_mcp=False,
        supports_native_tools=True,
        supports_hooks=False,
        supports_stateful_client=False,
        supports_output_schema=True,
        supports_system_prompt_file=False,
        supports_streaming=True,
    )
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (ApiKey,)

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        cred = auth.resolve()
        import mistral_sdk
        self._client = mistral_sdk.Client(api_key=cred.payload["api_key"])

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        sp = self._translate_system_prompt(options.system_prompt)
        tools = self._translate_tools(options.tool_policy)
        async for raw in self._client.stream(prompt=prompt, system=sp, tools=tools):
            yield Message(text=raw.text, is_final=raw.final, raw=raw)

    def client(self, options: ProviderOptions):
        raise UnsupportedCapabilityError(
            provider=self.name, capability="stateful_client"
        )

    def _translate_system_prompt(self, sp: SystemPrompt) -> str:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            raise UnsupportedCapabilityError(
                provider=self.name, capability="system_prompt_file"
            )
        raise NotImplementedError(f"Unknown SystemPrompt: {type(sp)}")

    def _translate_tools(self, policy: ToolPolicy) -> list[dict]:
        return [{"name": t.name, "schema": t.input_schema} for t in policy.custom]

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> Any:
        if servers:
            raise UnsupportedCapabilityError(provider=self.name, capability="mcp")
        return None
```

### 3.2 Add the side-effect import

In `src/llm_providers/providers/__init__.py`:

```python
from llm_providers.providers import mistral  # noqa: F401
```

That's the only edit to existing code.

### 3.3 Add an optional dependency

In the project's `pyproject.toml`:

```toml
[project.optional-dependencies]
mistral = ["mistral-sdk>=1.0"]
```

## Adding a new auth strategy

### 4.1 Create the file

`src/llm_providers/auth/oauth2_device_code.py`:

```python
import os
from pathlib import Path
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed
from llm_providers.registry import AuthRegistry


@AuthRegistry.register("oauth2_device_code")
class OAuth2DeviceCode(AuthStrategy):
    kind = "oauth2_device_code"

    def __init__(self, token_path: Path | None = None) -> None:
        self._path = token_path or Path.home() / ".myvendor" / "device_token.json"

    @classmethod
    def default(cls) -> "OAuth2DeviceCode":
        return cls()

    def detect(self) -> bool:
        return self._path.exists()

    def resolve(self) -> Credential:
        if not self._path.exists():
            raise AuthDetectionFailed(f"{self._path} not found")
        token = self._path.read_text().strip()
        return Credential(kind=self.kind, payload={"token": token})
```

### 4.2 Wire it into a provider

In whichever providers should accept it:

```python
from llm_providers.auth.oauth2_device_code import OAuth2DeviceCode

class MyProvider(BaseProvider):
    supported_auth = (OAuth2DeviceCode, ApiKey)  # preferred-first
```

And add one line to `src/llm_providers/auth/__init__.py`:

```python
from llm_providers.auth.oauth2_device_code import OAuth2DeviceCode  # noqa: F401
```

## Capability flags — when to flip each

| Flag | Set to True when … |
|---|---|
| `supports_mcp` | The provider can register MCP servers and call them mid-conversation. |
| `supports_native_tools` | The provider supports function-calling / tool-use. |
| `supports_hooks` | The provider supports event hooks (currently Claude-only). |
| `supports_stateful_client` | The provider exposes a multi-turn session object (vs. one-shot only). |
| `supports_output_schema` | The provider validates/conforms the final response against a JSON Schema. |
| `supports_system_prompt_file` | The provider has a native file-based or named-preset system prompt mechanism. |
| `supports_streaming` | The provider's query() emits incremental Messages before is_final=True. |

## Translation hooks — contract

| Hook | Input | Must return | Raises |
|---|---|---|---|
| `_translate_system_prompt` | `SystemPrompt` (sum type) | Native SDK system-prompt value | `UnsupportedCapabilityError` for `PresetSystemPrompt` if `supports_system_prompt_file=False`. `TranslationError` for unknown subtypes. |
| `_translate_tools` | `ToolPolicy` | Native SDK tools shape (dict / list, vendor-specific) | `UnsupportedCapabilityError` if policy.custom is non-empty and `supports_native_tools=False`. |
| `_translate_mcp` | `tuple[McpServerSpec, ...]` | Native SDK MCP shape | `UnsupportedCapabilityError` if servers is non-empty and `supports_mcp=False`. |

## Error model — which exception to raise when

| Situation | Exception |
|---|---|
| Caller used a feature the provider doesn't expose | `UnsupportedCapabilityError(provider, capability)` |
| Caller passed an AuthStrategy not in `supported_auth` | `UnsupportedAuthError(provider, got, accepted)` (raised by `BaseProvider`) |
| `auto_resolve_auth` exhausted `supported_auth` | `AuthResolutionError(provider, skipped, accepted)` |
| `detect()` returned True but `resolve()` then failed | `AuthDetectionFailed` (from inside `resolve`) |
| Provider received a Credential it doesn't know how to apply | `CredentialMismatch` |
| `_translate_*` produced invalid native output | `TranslationError` |
| SDK raised during `query()` or `client()` | `ProviderRuntimeError(provider, phase)` with `__cause__` set |

## Testing your provider

1. **Conformance suite** (`tests/llm_providers/test_conformance.py`) — runs automatically against every registered provider. Your provider is included as soon as the side-effect import line is added.
2. **Per-provider unit tests** — `tests/llm_providers/providers/test_<name>.py`. Cover translation hooks (one test per `SystemPrompt` subtype + each tools/MCP edge case) and SDK error wrapping (`ProviderRuntimeError` with correct `__cause__`).
3. **Auth strategy tests** — `tests/llm_providers/auth/test_<kind>.py`. Cover `detect()` true/false matrix and `resolve()` happy path + failure path.

## Do / Don't

**Do:**
- Lazy-import the vendor SDK inside `__init__` / methods, not at module top.
- Raise `UnsupportedCapabilityError` early — don't silently swallow features.
- Document your provider's recognized `extras` keys in the class docstring.
- Use `Credential.payload` as an opaque dict; provider reads what it needs by `kind`.

**Don't:**
- Import from `hsb.*` (CI enforces this via AST check).
- Write to the operator's vendor config files. The library reads; the operator writes.
- Mutate process-wide env vars without scoping. Where the SDK requires an env var, set it from the credential at provider init; don't expect callers to set it.
- Add provider-specific options to `ProviderOptions`. Use `extras[<provider name>]` instead.

## PR-ready checklist

- [ ] New provider file lives in `src/llm_providers/providers/<name>.py`
- [ ] `@ProviderRegistry.register("<name>")` decorator applied
- [ ] `name` ClassVar matches the decorator argument
- [ ] `capabilities` flags reviewed against the table above
- [ ] `supported_auth` declared, ordered preferred-first
- [ ] `query()` and `client()` implemented (or `client()` raises UnsupportedCapabilityError)
- [ ] All three `_translate_*` hooks implemented (or raise UnsupportedCapabilityError)
- [ ] Side-effect import added to `providers/__init__.py`
- [ ] SDK declared as optional extra in `pyproject.toml`
- [ ] Conformance test suite passes for the new provider
- [ ] Unit tests for each `_translate_*` hook
- [ ] Auth detection test covering each accepted strategy
- [ ] No imports from `hsb.*` (library remains decoupled)

## Reference

- Design spec: `docs/superpowers/specs/2026-05-11-multi-provider-module-design.md`
