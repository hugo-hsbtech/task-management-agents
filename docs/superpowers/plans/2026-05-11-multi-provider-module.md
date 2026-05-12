# Multi-Provider LLM Module — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a decoupled `src/llm_providers/` library with two registered providers (Claude, OpenAI) and rewire `src/hsb/runtime/` as a thin consumer. All existing tests pass via compat shims; new conformance suite covers the library.

**Architecture:** Library is policy-free, OOP-driven, OCP-compliant via decorator registries (`ProviderRegistry`, `AuthRegistry`). Providers are `BaseProvider(ABC)` subclasses declaring `capabilities` (ClassVar dataclass) and `supported_auth` (ordered tuple of `AuthStrategy` classes). Authentication is the Strategy pattern. `OpenAIProvider` is a single class with two internal backends (`_CodexBackend` for Codex CLI OAuth, `_RawOpenAIBackend` for `OPENAI_API_KEY`). hsb-side policy (G1 OAuth2-only, G2 forbidden tools, G3 Task-tool backstop) stays in `hsb.runtime.policy` and `hsb.runtime.handle`.

**Tech Stack:** Python 3.12, `claude-agent-sdk`, `openai-codex-sdk`, `openai`, `pytest` + `pytest-asyncio`, hatchling.

**Spec:** `docs/superpowers/specs/2026-05-11-multi-provider-module-design.md`

**Out of scope for Phase A (covered by later plans):**
- Gemini provider + Google auth strategies (Phase B plan)
- Migrating UAT/Risk/Linear/Git/QA/Builder/Intelligence agents from direct SDK to runtime adapter (Phase C, one plan per agent)
- Standalone PyPI extraction
- Built-in fallback / orchestration patterns

---

## File Structure

### Created (library — `src/llm_providers/`)

| File | Responsibility |
|---|---|
| `src/llm_providers/__init__.py` | Public surface; triggers provider registration via side-effect import. |
| `src/llm_providers/README.md` | Contributor onboarding — how to add a provider / auth strategy. |
| `src/llm_providers/protocol.py` | `Message`, `Capabilities`, `ProviderOptions`, `PermissionMode`. |
| `src/llm_providers/errors.py` | `LLMProvidersError` hierarchy. |
| `src/llm_providers/prompt.py` | `SystemPrompt` sum type: `TextSystemPrompt`, `SkillReference`, `PresetSystemPrompt`. |
| `src/llm_providers/tools.py` | `ToolSpec`, `ToolPolicy`, `McpServerSpec`. |
| `src/llm_providers/base.py` | `BaseProvider(ABC)`, `StatefulClient` Protocol. |
| `src/llm_providers/registry.py` | `ProviderRegistry`, `AuthRegistry`, `auto_resolve_auth`. |
| `src/llm_providers/auth/__init__.py` | Re-exports + triggers strategy registration. |
| `src/llm_providers/auth/base.py` | `AuthStrategy(ABC)`, `Credential`. |
| `src/llm_providers/auth/api_key.py` | `ApiKey` strategy. |
| `src/llm_providers/auth/oauth2_cli.py` | `OAuth2CliToken` strategy. |
| `src/llm_providers/providers/__init__.py` | Side-effect imports of all provider modules. |
| `src/llm_providers/providers/claude.py` | `ClaudeProvider` + Claude `StatefulClient` wrapper. |
| `src/llm_providers/providers/openai.py` | `OpenAIProvider` with `_CodexBackend` + `_RawOpenAIBackend`. |
| `src/llm_providers/providers/_codex_config.py` | Codex `~/.codex/config.toml` parsing + OAuth-only verification (ported from `hsb.runtime.codex_guards`). |

### Modified (hsb consumer — `src/hsb/runtime/`)

| File | Change |
|---|---|
| `src/hsb/runtime/__init__.py` | Re-export the now-aliased types from `hsb.runtime.protocol`. |
| `src/hsb/runtime/protocol.py` | `AgentOptions = ProviderOptions` (TypeAlias); `Message` re-exported; `Runtime` Protocol kept as deprecation alias for `BaseProvider`. |
| `src/hsb/runtime/policy.py` | **NEW** — G1 OAuth2-only allowlist + `HSB_AUTH_ALLOW_API_KEY_<AGENT>` escape hatch. |
| `src/hsb/runtime/resolver.py` | **NEW** — data-driven `resolve_runtime(agent)` returning `HsbProviderHandle`. Hard-block dict for WIO. |
| `src/hsb/runtime/handle.py` | **NEW** — `HsbProviderHandle` wraps a `BaseProvider`, applies G3 backstop on every message. |
| `src/hsb/runtime/compat.py` | **NEW** — `ClaudeRuntime` and `CodexRuntime` deprecation shims for legacy imports. |
| `src/hsb/runtime/claude.py` | Replace with thin re-export from `compat.py` for backward compat. |
| `src/hsb/runtime/codex.py` | Replace with thin re-export from `compat.py` for backward compat. |
| `src/hsb/runtime/codex_guards.py` | Keep as a thin re-export from `llm_providers.providers._codex_config` so existing tests pass. |
| `src/hsb/agents/_sdk_options.py` | `assert_oauth2_only()` delegates to `policy.allowed_auth_kinds()`. `resolve_runtime()` becomes one-liner calling `hsb.runtime.resolver.resolve_runtime()`. `make_options()` and `make_agent_options()` signatures unchanged. |
| `pyproject.toml` | `[tool.hatch.build.targets.wheel] packages = ["src/hsb", "src/llm_providers"]`. |

### Created (tests)

| File | Coverage |
|---|---|
| `tests/llm_providers/__init__.py` | Package marker. |
| `tests/llm_providers/test_protocol.py` | `Message`, `Capabilities`, `ProviderOptions` shape + frozen invariants. |
| `tests/llm_providers/test_errors.py` | Exception hierarchy + attrs. |
| `tests/llm_providers/test_prompt.py` | `SystemPrompt` subclasses, frozen. |
| `tests/llm_providers/test_tools.py` | `ToolPolicy`, `ToolSpec`, `McpServerSpec`. |
| `tests/llm_providers/test_base.py` | `BaseProvider._validate_auth`, abstract enforcement, `require_capability`. |
| `tests/llm_providers/test_registry.py` | `ProviderRegistry`/`AuthRegistry`: register, get, build, build_auto, duplicates, name mismatch. |
| `tests/llm_providers/test_auth_resolution.py` | `auto_resolve_auth` walk + `accepted_kinds` filter + `AuthResolutionError` detail. |
| `tests/llm_providers/test_conformance.py` | Parametrized over `ProviderRegistry.names()` — Liskov contract assertions + `no hsb import` AST check. |
| `tests/llm_providers/auth/__init__.py` | Package marker. |
| `tests/llm_providers/auth/test_base.py` | `AuthStrategy` ABC + `Credential`. |
| `tests/llm_providers/auth/test_api_key.py` | `ApiKey` detect/resolve/default. |
| `tests/llm_providers/auth/test_oauth2_cli.py` | `OAuth2CliToken` env-var + file-based detect/resolve. |
| `tests/llm_providers/providers/__init__.py` | Package marker. |
| `tests/llm_providers/providers/test_claude.py` | `ClaudeProvider` translation hooks + auth wiring (mocked SDK). |
| `tests/llm_providers/providers/test_openai.py` | `OpenAIProvider` dual-backend routing (mocked SDKs). |
| `tests/llm_providers/providers/test_codex_config.py` | `_codex_config` OAuth-only verification + MCP verification (ported from `test_codex_guards.py`). |
| `tests/runtime/test_policy.py` | G1 allowlist defaults + per-agent API-key escape hatch. |
| `tests/runtime/test_resolver.py` | Env-var routing, hard-blocks, `codex` → `openai` deprecation alias. |
| `tests/runtime/test_handle.py` | `HsbProviderHandle.query()` G3 fires on Task-tool message. |

---

## Conventions used in this plan

- All tests use `pytest` + `pytest-asyncio` (already configured: `asyncio_mode = "auto"` in `pyproject.toml`).
- Imports in tests follow the project convention: absolute imports rooted at `llm_providers` or `hsb`.
- TDD cadence per task: write failing test → run (red) → implement → run (green) → commit.
- Commit messages use Conventional Commits as the existing repo does.
- After every task, run `ruff check src/ tests/ && mypy src/` to catch lint/type drift before commit. Where this would add noise to the plan, it is included as the last step before commit.

---

## Task 1: Library skeleton + `protocol.py`

**Files:**
- Create: `src/llm_providers/__init__.py`
- Create: `src/llm_providers/protocol.py`
- Create: `tests/llm_providers/__init__.py`
- Create: `tests/llm_providers/test_protocol.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/test_protocol.py`:
```python
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
    with pytest.raises(Exception):
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
    with pytest.raises(Exception):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_protocol.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers'`

- [ ] **Step 3: Create the package skeleton**

`src/llm_providers/__init__.py`:
```python
"""llm_providers — decoupled multi-provider LLM library.

Public surface is re-exported from this module. Importing this package
also triggers provider and auth-strategy registration as a side effect.
"""
from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)

__all__ = [
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
]
```

`src/llm_providers/protocol.py`:
```python
"""Core protocol types — minimal shape every provider satisfies."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_providers.prompt import SystemPrompt
    from llm_providers.tools import McpServerSpec, ToolPolicy


PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


@dataclass(frozen=True)
class Message:
    """Minimal message shape yielded by every provider's query() iterator."""
    text: str
    is_final: bool = False
    raw: Any = None


@dataclass(frozen=True)
class Capabilities:
    """Per-provider capability flags. Callers check these before requesting
    a feature; providers raise UnsupportedCapabilityError when a flag is
    False and the feature is exercised."""
    supports_mcp: bool
    supports_native_tools: bool
    supports_hooks: bool
    supports_stateful_client: bool
    supports_output_schema: bool
    supports_system_prompt_file: bool
    supports_streaming: bool
    max_context_tokens: int | None = None


@dataclass(frozen=True)
class ProviderOptions:
    """Vendor-neutral options. Translated to each provider's native shape
    by its _translate_* hooks."""
    system_prompt: "SystemPrompt"
    model: str
    max_turns: int
    tool_policy: "ToolPolicy"
    mcp_servers: tuple["McpServerSpec", ...] = ()
    permission_mode: PermissionMode = "default"
    output_schema: dict | None = None
    cwd: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)
```

`tests/llm_providers/__init__.py`: empty file.

- [ ] **Step 4: Create stubs for prompt.py and tools.py so the test imports resolve**

`src/llm_providers/prompt.py`:
```python
"""SystemPrompt sum type — see Task 3 for full implementation."""
from __future__ import annotations
from abc import ABC
from dataclasses import dataclass


class SystemPrompt(ABC):
    """Base class for the SystemPrompt sum type."""


@dataclass(frozen=True)
class TextSystemPrompt(SystemPrompt):
    text: str
```

`src/llm_providers/tools.py`:
```python
"""Tool/MCP shapes — see Task 4 for full implementation."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPolicy:
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
```

(These are minimal stubs — Tasks 3 and 4 expand them with full subclasses and validation.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_protocol.py -v`
Expected: 5 passed.

- [ ] **Step 6: Lint + types + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/__init__.py src/llm_providers/protocol.py \
        src/llm_providers/prompt.py src/llm_providers/tools.py \
        tests/llm_providers/__init__.py tests/llm_providers/test_protocol.py
git commit -m "feat(llm_providers): protocol types — Message, Capabilities, ProviderOptions"
```

---

## Task 2: Error hierarchy

**Files:**
- Create: `src/llm_providers/errors.py`
- Create: `tests/llm_providers/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/test_errors.py`:
```python
"""Error hierarchy and attribute tests."""
import pytest

from llm_providers.errors import (
    AuthDetectionFailed,
    AuthResolutionError,
    CredentialMismatch,
    LLMProvidersError,
    ProviderNotFoundError,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedAuthError,
    UnsupportedCapabilityError,
)


def test_all_errors_subclass_root():
    for cls in (
        ProviderNotFoundError,
        UnsupportedAuthError,
        UnsupportedCapabilityError,
        AuthResolutionError,
        AuthDetectionFailed,
        CredentialMismatch,
        TranslationError,
        ProviderRuntimeError,
    ):
        assert issubclass(cls, LLMProvidersError)


def test_provider_not_found_error_attrs():
    err = ProviderNotFoundError(name="nope", available=("claude", "openai"))
    assert err.name == "nope"
    assert err.available == ("claude", "openai")
    assert "nope" in str(err)
    assert "claude" in str(err)


def test_unsupported_auth_error_attrs():
    err = UnsupportedAuthError(
        provider="claude", got="OAuth2Adc", accepted=["OAuth2CliToken", "ApiKey"]
    )
    assert err.provider == "claude"
    assert err.got == "OAuth2Adc"
    assert err.accepted == ["OAuth2CliToken", "ApiKey"]


def test_unsupported_capability_error_attrs():
    err = UnsupportedCapabilityError(provider="gemini", capability="mcp")
    assert err.provider == "gemini"
    assert err.capability == "mcp"
    assert "gemini" in str(err) and "mcp" in str(err)


def test_auth_resolution_error_attrs():
    err = AuthResolutionError(
        provider="gemini",
        skipped=[("OAuth2CliToken", "not_detected"), ("ApiKey", "filtered_by_accepted_kinds")],
        accepted={"oauth2_adc"},
    )
    assert err.provider == "gemini"
    assert len(err.skipped) == 2
    assert err.accepted == {"oauth2_adc"}


def test_provider_runtime_error_carries_cause():
    inner = ValueError("sdk blew up")
    err = ProviderRuntimeError(provider="claude", phase="query")
    try:
        raise err from inner
    except ProviderRuntimeError as caught:
        assert caught.__cause__ is inner
        assert caught.provider == "claude"
        assert caught.phase == "query"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.errors'`

- [ ] **Step 3: Implement the error hierarchy**

`src/llm_providers/errors.py`:
```python
"""Exception hierarchy for the llm_providers library.

Library raises only LLMProvidersError subclasses. SDK exceptions are
wrapped in ProviderRuntimeError with __cause__ set to the original.
"""
from __future__ import annotations

from collections.abc import Iterable


class LLMProvidersError(Exception):
    """Root of all library-defined errors."""


class ProviderNotFoundError(LLMProvidersError):
    """Raised when ProviderRegistry.get(name) is called for an unregistered name."""

    def __init__(self, name: str, available: tuple[str, ...]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Provider {name!r} is not registered. "
            f"Available providers: {available}."
        )


class UnsupportedAuthError(LLMProvidersError):
    """Caller passed an AuthStrategy not declared in provider.supported_auth."""

    def __init__(self, provider: str, got: str, accepted: list[str]) -> None:
        self.provider = provider
        self.got = got
        self.accepted = accepted
        super().__init__(
            f"Provider {provider!r} does not accept auth strategy {got!r}. "
            f"Accepted: {accepted}."
        )


class UnsupportedCapabilityError(LLMProvidersError):
    """Caller exercised a feature the provider does not expose."""

    def __init__(self, provider: str, capability: str) -> None:
        self.provider = provider
        self.capability = capability
        super().__init__(
            f"Provider {provider!r} does not support capability {capability!r}."
        )


class AuthResolutionError(LLMProvidersError):
    """auto_resolve_auth exhausted provider.supported_auth without a match."""

    def __init__(
        self,
        provider: str,
        skipped: list[tuple[str, str]],
        accepted: set[str] | None,
    ) -> None:
        self.provider = provider
        self.skipped = skipped
        self.accepted = accepted
        detail = "; ".join(f"{name}: {reason}" for name, reason in skipped)
        super().__init__(
            f"Could not resolve any auth strategy for provider {provider!r}. "
            f"Accepted kinds: {accepted}. Tried: [{detail}]."
        )


class AuthDetectionFailed(LLMProvidersError):
    """Strategy.detect() returned True but resolve() then failed.

    Raised by an AuthStrategy.resolve() so auto_resolve_auth can record it
    and continue the walk instead of bubbling."""


class CredentialMismatch(LLMProvidersError):
    """Provider received a Credential whose kind it doesn't know how to apply.

    Defense-in-depth against AuthStrategy/Provider drift."""


class TranslationError(LLMProvidersError):
    """A _translate_* hook produced an invalid native option object."""


class ProviderRuntimeError(LLMProvidersError):
    """Wraps an SDK exception raised during query()/client().

    The original SDK exception is on __cause__."""

    def __init__(self, provider: str, phase: str) -> None:
        self.provider = provider
        self.phase = phase
        super().__init__(
            f"Provider {provider!r} raised during {phase!r}. See __cause__ for details."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_errors.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/errors.py tests/llm_providers/test_errors.py
git commit -m "feat(llm_providers): exception hierarchy"
```

---

## Task 3: `SystemPrompt` sum type

**Files:**
- Modify: `src/llm_providers/prompt.py`
- Create: `tests/llm_providers/test_prompt.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/test_prompt.py`:
```python
"""SystemPrompt sum-type shape tests."""
from pathlib import Path

import pytest

from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)


def test_all_three_subclass_systemprompt():
    assert issubclass(TextSystemPrompt, SystemPrompt)
    assert issubclass(SkillReference, SystemPrompt)
    assert issubclass(PresetSystemPrompt, SystemPrompt)


def test_text_is_frozen():
    p = TextSystemPrompt(text="hi")
    with pytest.raises(Exception):
        p.text = "x"  # type: ignore[misc]


def test_skill_reference_holds_path_and_optional_locator(tmp_path):
    p = SkillReference(path=tmp_path / "skill.md")
    assert p.path == tmp_path / "skill.md"
    assert p.locator is None
    p2 = SkillReference(path=Path("/tmp/x.md"), locator=".claude/skills/foo/SKILL.md")
    assert p2.locator == ".claude/skills/foo/SKILL.md"


def test_preset_holds_id():
    p = PresetSystemPrompt(preset_id="my-preset")
    assert p.preset_id == "my-preset"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_prompt.py -v`
Expected: `ImportError: cannot import name 'PresetSystemPrompt' from 'llm_providers.prompt'`

- [ ] **Step 3: Implement the full module (replacing the stub from Task 1)**

`src/llm_providers/prompt.py`:
```python
"""SystemPrompt sum type — first-class support for vendor-neutral skills.

Three subclasses:
  - TextSystemPrompt:    raw string content.
  - SkillReference:      path to a markdown skill file. Provider decides
                         whether to load natively (Claude SystemPromptFile)
                         or read-and-inline (Codex / Gemini).
  - PresetSystemPrompt:  named preset; only valid for providers whose
                         capabilities.supports_system_prompt_file is True.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from pathlib import Path


class SystemPrompt(ABC):
    """Base of the SystemPrompt sum type. Subclass-based discriminated union."""


@dataclass(frozen=True)
class TextSystemPrompt(SystemPrompt):
    text: str


@dataclass(frozen=True)
class SkillReference(SystemPrompt):
    """Path to a markdown skill file (e.g. .claude/skills/uat-validation/SKILL.md).

    `locator` is an optional human-readable identifier (typically the project-
    relative path) used for logging/observability. Not required for resolution.
    """
    path: Path
    locator: str | None = None


@dataclass(frozen=True)
class PresetSystemPrompt(SystemPrompt):
    """Vendor-managed named preset (e.g. claude_agent_sdk.SystemPromptPreset).

    Only valid when provider.capabilities.supports_system_prompt_file is True.
    Providers without native preset support raise UnsupportedCapabilityError.
    """
    preset_id: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_prompt.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/prompt.py tests/llm_providers/test_prompt.py
git commit -m "feat(llm_providers): SystemPrompt sum type (Text, Skill, Preset)"
```

---

## Task 4: `ToolPolicy` + `McpServerSpec`

**Files:**
- Modify: `src/llm_providers/tools.py`
- Create: `tests/llm_providers/test_tools.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/test_tools.py`:
```python
"""Tool / MCP shape tests."""
import pytest

from llm_providers.tools import McpServerSpec, ToolPolicy, ToolSpec


def test_tool_spec_is_frozen():
    t = ToolSpec(name="read", description="read a file", input_schema={"type": "object"})
    with pytest.raises(Exception):
        t.name = "x"  # type: ignore[misc]
    assert t.handler is None


def test_tool_policy_defaults_empty():
    p = ToolPolicy()
    assert p.allowed == ()
    assert p.denied == ()
    assert p.custom == ()


def test_tool_policy_can_carry_custom_tools():
    spec = ToolSpec(name="myfn", description="d", input_schema={})
    p = ToolPolicy(custom=(spec,))
    assert p.custom[0] is spec


def test_mcp_server_stdio():
    s = McpServerSpec(name="filesystem", transport="stdio", command=("npx", "fs-mcp"))
    assert s.transport == "stdio"
    assert s.url is None
    assert s.env == {}


def test_mcp_server_http():
    s = McpServerSpec(name="api", transport="http", url="http://localhost:8000")
    assert s.command is None
    assert s.url == "http://localhost:8000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_tools.py -v`
Expected: `ImportError: cannot import name 'ToolSpec' from 'llm_providers.tools'`

- [ ] **Step 3: Implement the full module**

`src/llm_providers/tools.py`:
```python
"""Vendor-neutral tool and MCP shapes.

Translated by each provider's _translate_tools / _translate_mcp hook into
the native SDK form. Providers that don't support a given concept raise
UnsupportedCapabilityError via require_capability().
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolSpec:
    """A vendor-neutral tool/function declaration.

    For in-process tools (handler is not None), the provider wires the
    handler into its tool-call dispatch. For declaration-only tools
    (handler is None), the provider only exposes the schema to the model.
    """
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Awaitable[Any]] | None = None


@dataclass(frozen=True)
class ToolPolicy:
    """Whitelist / denylist + custom tool declarations.

    `allowed` and `denied` use vendor-neutral tool names. Provider translates
    to the SDK's allowed_tools mechanism. `custom` lets the caller declare
    function-calling tools without going through MCP.
    """
    allowed: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    custom: tuple[ToolSpec, ...] = ()


@dataclass(frozen=True)
class McpServerSpec:
    """An MCP server registration.

    `transport="stdio"` requires `command`; `transport="http"` requires `url`.
    Validation is done by the provider's _translate_mcp hook.
    """
    name: str
    transport: Literal["stdio", "http"]
    command: tuple[str, ...] | None = None
    url: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_tools.py -v`
Expected: 5 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/tools.py tests/llm_providers/test_tools.py
git commit -m "feat(llm_providers): ToolPolicy, ToolSpec, McpServerSpec"
```

---

## Task 5: `AuthStrategy` base + `Credential`

**Files:**
- Create: `src/llm_providers/auth/__init__.py`
- Create: `src/llm_providers/auth/base.py`
- Create: `tests/llm_providers/auth/__init__.py`
- Create: `tests/llm_providers/auth/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/auth/test_base.py`:
```python
"""AuthStrategy ABC + Credential shape tests."""
import pytest

from llm_providers.auth.base import AuthStrategy, Credential


def test_credential_is_frozen():
    c = Credential(kind="api_key", payload={"key": "secret"})
    with pytest.raises(Exception):
        c.kind = "oauth2_cli_token"  # type: ignore[misc]


def test_auth_strategy_cannot_be_instantiated_directly():
    with pytest.raises(TypeError, match="abstract"):
        AuthStrategy()  # type: ignore[abstract]


def test_auth_strategy_subclass_must_implement_methods():
    class Incomplete(AuthStrategy):
        kind = "incomplete"
    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # type: ignore[abstract]


def test_auth_strategy_full_subclass_constructs():
    class Full(AuthStrategy):
        kind = "full"
        def detect(self) -> bool:
            return True
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls) -> "Full":
            return cls()

    f = Full()
    assert f.detect() is True
    assert f.resolve().kind == "full"
    assert isinstance(Full.default(), Full)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/auth/test_base.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.auth'`

- [ ] **Step 3: Implement `auth/base.py`**

`src/llm_providers/auth/base.py`:
```python
"""AuthStrategy ABC + Credential dataclass.

Each strategy resolves a credential from one source (env var, file, gcloud
ADC, etc.). Providers declare their supported_auth as an ordered tuple of
strategy classes; the registry's auto_resolve_auth walks the tuple in
preferred-first order.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal


@dataclass(frozen=True)
class Credential:
    """Resolved credential. Opaque to general callers; providers read what
    they need from `payload` based on `kind`."""
    kind: Literal["api_key", "oauth2_cli_token", "oauth2_adc", "oauth2_service_account"]
    payload: Mapping[str, Any]


class AuthStrategy(ABC):
    """Strategy interface — one instance == one resolved credential source.

    Lifecycle:
      1. detect()  — cheap check: is this strategy available in the environment?
      2. resolve() — full resolution; may read files, refresh tokens.
      3. default() — classmethod returning the conventional zero-arg form
                     used by auto_resolve_auth.
    """
    kind: ClassVar[str]

    @abstractmethod
    def detect(self) -> bool: ...

    @abstractmethod
    def resolve(self) -> Credential: ...

    @classmethod
    @abstractmethod
    def default(cls) -> "AuthStrategy": ...
```

`src/llm_providers/auth/__init__.py`:
```python
"""Auth strategies. Importing this package triggers strategy registration."""
from llm_providers.auth.base import AuthStrategy, Credential

__all__ = ["AuthStrategy", "Credential"]
```

`tests/llm_providers/auth/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/auth/test_base.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/auth/ tests/llm_providers/auth/__init__.py tests/llm_providers/auth/test_base.py
git commit -m "feat(llm_providers): AuthStrategy ABC + Credential"
```

---

## Task 6: `ApiKey` auth strategy

**Files:**
- Create: `src/llm_providers/auth/api_key.py`
- Modify: `src/llm_providers/auth/__init__.py`
- Create: `tests/llm_providers/auth/test_api_key.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/auth/test_api_key.py`:
```python
"""ApiKey strategy: env-var detection + resolution."""
import pytest

from llm_providers.auth.api_key import ApiKey


def test_detect_true_when_env_var_set(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret-value")
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is True


def test_detect_false_when_env_var_absent(monkeypatch):
    monkeypatch.delenv("MY_KEY", raising=False)
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is False


def test_detect_false_when_env_var_empty(monkeypatch):
    monkeypatch.setenv("MY_KEY", "")
    s = ApiKey(env_var="MY_KEY")
    assert s.detect() is False


def test_resolve_returns_credential(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret-value")
    s = ApiKey(env_var="MY_KEY")
    cred = s.resolve()
    assert cred.kind == "api_key"
    assert cred.payload["api_key"] == "secret-value"
    assert cred.payload["env_var"] == "MY_KEY"


def test_resolve_raises_when_env_var_absent(monkeypatch):
    from llm_providers.errors import AuthDetectionFailed
    monkeypatch.delenv("MY_KEY", raising=False)
    s = ApiKey(env_var="MY_KEY")
    with pytest.raises(AuthDetectionFailed):
        s.resolve()


def test_default_uses_class_default_env_var(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "x")
    s = ApiKey.default()
    assert s.detect() is True


def test_kind_classvar():
    assert ApiKey.kind == "api_key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/auth/test_api_key.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.auth.api_key'`

- [ ] **Step 3: Implement `ApiKey`**

`src/llm_providers/auth/api_key.py`:
```python
"""ApiKey auth strategy — literal key from an env var."""
from __future__ import annotations

import os
from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed


class ApiKey(AuthStrategy):
    """API-key credential read from an environment variable.

    Construction:
      ApiKey(env_var="ANTHROPIC_API_KEY")  — explicit
      ApiKey.default()                     — uses LLM_PROVIDERS_API_KEY
                                             (callers usually pass explicit
                                             env_var; default() exists for
                                             auto_resolve_auth's walk).
    """
    kind: ClassVar[str] = "api_key"
    _DEFAULT_ENV_VAR: ClassVar[str] = "LLM_PROVIDERS_API_KEY"

    def __init__(self, env_var: str = _DEFAULT_ENV_VAR) -> None:
        self._env_var = env_var

    def detect(self) -> bool:
        return bool(os.environ.get(self._env_var))

    def resolve(self) -> Credential:
        value = os.environ.get(self._env_var)
        if not value:
            raise AuthDetectionFailed(
                f"ApiKey: env var {self._env_var!r} is not set or empty."
            )
        return Credential(
            kind=self.kind,
            payload={"api_key": value, "env_var": self._env_var},
        )

    @classmethod
    def default(cls) -> "ApiKey":
        return cls()
```

Modify `src/llm_providers/auth/__init__.py`:
```python
"""Auth strategies. Importing this package triggers strategy registration."""
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.api_key import ApiKey

__all__ = ["ApiKey", "AuthStrategy", "Credential"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/auth/test_api_key.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/auth/api_key.py src/llm_providers/auth/__init__.py \
        tests/llm_providers/auth/test_api_key.py
git commit -m "feat(llm_providers): ApiKey auth strategy"
```

---

## Task 7: `OAuth2CliToken` auth strategy

**Files:**
- Create: `src/llm_providers/auth/oauth2_cli.py`
- Modify: `src/llm_providers/auth/__init__.py`
- Create: `tests/llm_providers/auth/test_oauth2_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/auth/test_oauth2_cli.py`:
```python
"""OAuth2CliToken strategy: env-var OR file-based detection."""
import json
from pathlib import Path

import pytest

from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import AuthDetectionFailed


def test_kind_classvar():
    assert OAuth2CliToken.kind == "oauth2_cli_token"


def test_detect_env_var_present(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "tok-abc")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    assert s.detect() is True


def test_detect_env_var_empty(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    assert s.detect() is False


def test_detect_token_file_present(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.json"
    f.write_text(json.dumps({"access_token": "tok-xyz"}))
    s = OAuth2CliToken(token_path=f)
    assert s.detect() is True


def test_detect_token_file_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    s = OAuth2CliToken(token_path=tmp_path / "missing.json")
    assert s.detect() is False


def test_resolve_env_var_returns_token(monkeypatch):
    monkeypatch.setenv("MY_OAUTH", "tok-abc")
    s = OAuth2CliToken(env_var="MY_OAUTH")
    cred = s.resolve()
    assert cred.kind == "oauth2_cli_token"
    assert cred.payload["token"] == "tok-abc"
    assert cred.payload["source"] == "env:MY_OAUTH"


def test_resolve_file_returns_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.json"
    f.write_text(json.dumps({"access_token": "tok-xyz"}))
    s = OAuth2CliToken(token_path=f)
    cred = s.resolve()
    assert cred.payload["token"] == "tok-xyz"
    assert cred.payload["source"] == f"file:{f}"


def test_resolve_file_plain_text(tmp_path, monkeypatch):
    """If the file is not JSON, treat its contents as the raw token."""
    monkeypatch.delenv("MY_OAUTH", raising=False)
    f = tmp_path / "token.txt"
    f.write_text("raw-token-string\n")
    s = OAuth2CliToken(token_path=f)
    cred = s.resolve()
    assert cred.payload["token"] == "raw-token-string"


def test_resolve_raises_when_nothing_available(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_OAUTH", raising=False)
    s = OAuth2CliToken(env_var="MY_OAUTH", token_path=tmp_path / "missing.json")
    with pytest.raises(AuthDetectionFailed):
        s.resolve()


def test_default_constructs_without_args():
    # default() must not require an env var or path; detect() returns False
    # when neither is configured.
    s = OAuth2CliToken.default()
    assert isinstance(s, OAuth2CliToken)
    assert s.detect() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/auth/test_oauth2_cli.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.auth.oauth2_cli'`

- [ ] **Step 3: Implement `OAuth2CliToken`**

`src/llm_providers/auth/oauth2_cli.py`:
```python
"""OAuth2CliToken auth strategy — token written by a vendor CLI.

Reads from one of:
  - an environment variable (e.g. CLAUDE_CODE_OAUTH_TOKEN)
  - a token file (e.g. ~/.codex/auth.json, ~/.gemini/oauth.json)

If both are configured, env var wins. The file is parsed as JSON when possible
(looking for "access_token" or "token" keys); otherwise its raw contents are
treated as the token string.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.errors import AuthDetectionFailed


class OAuth2CliToken(AuthStrategy):
    """OAuth2 bearer token sourced from an env var or a CLI-managed file."""
    kind: ClassVar[str] = "oauth2_cli_token"

    def __init__(
        self,
        env_var: str | None = None,
        token_path: Path | None = None,
    ) -> None:
        self._env_var = env_var
        self._token_path = token_path

    @classmethod
    def default(cls) -> "OAuth2CliToken":
        # Caller must supply explicit env_var / token_path for detection to
        # succeed. default() exists so auto_resolve_auth can walk uniformly.
        return cls()

    def detect(self) -> bool:
        if self._env_var and os.environ.get(self._env_var):
            return True
        if self._token_path and self._token_path.exists():
            return True
        return False

    def resolve(self) -> Credential:
        if self._env_var:
            v = os.environ.get(self._env_var)
            if v:
                return Credential(
                    kind=self.kind,
                    payload={"token": v, "source": f"env:{self._env_var}"},
                )
        if self._token_path and self._token_path.exists():
            raw = self._token_path.read_text(encoding="utf-8").strip()
            token = self._extract_token(raw)
            return Credential(
                kind=self.kind,
                payload={"token": token, "source": f"file:{self._token_path}"},
            )
        raise AuthDetectionFailed(
            f"OAuth2CliToken: neither env_var={self._env_var!r} nor "
            f"token_path={self._token_path!r} resolved a usable token."
        )

    @staticmethod
    def _extract_token(raw: str) -> str:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(obj, dict):
            for key in ("access_token", "token"):
                if isinstance(obj.get(key), str):
                    return obj[key]
        # JSON but unknown shape — return the raw text. Providers can override
        # _extract_token via subclassing if a specific shape is required.
        return raw
```

Modify `src/llm_providers/auth/__init__.py`:
```python
"""Auth strategies. Importing this package triggers strategy registration."""
from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken

__all__ = ["ApiKey", "AuthStrategy", "Credential", "OAuth2CliToken"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/auth/test_oauth2_cli.py -v`
Expected: 10 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/auth/oauth2_cli.py src/llm_providers/auth/__init__.py \
        tests/llm_providers/auth/test_oauth2_cli.py
git commit -m "feat(llm_providers): OAuth2CliToken auth strategy"
```

---

## Task 8: `BaseProvider` ABC + `StatefulClient` Protocol

**Files:**
- Create: `src/llm_providers/base.py`
- Create: `tests/llm_providers/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/test_base.py`:
```python
"""BaseProvider ABC contract tests."""
from collections.abc import AsyncIterator

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.protocol import Capabilities, Message, ProviderOptions


def _make_caps(**overrides) -> Capabilities:
    defaults = dict(
        supports_mcp=False,
        supports_native_tools=False,
        supports_hooks=False,
        supports_stateful_client=False,
        supports_output_schema=False,
        supports_system_prompt_file=False,
        supports_streaming=False,
    )
    defaults.update(overrides)
    return Capabilities(**defaults)


class _DummyProvider(BaseProvider):
    name = "dummy"
    capabilities = _make_caps(supports_mcp=True)
    supported_auth = (ApiKey,)

    async def query(self, prompt: str, options: ProviderOptions) -> AsyncIterator[Message]:
        yield Message(text="ok", is_final=True)

    def client(self, options: ProviderOptions):
        raise NotImplementedError


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        BaseProvider(auth=ApiKey())  # type: ignore[abstract]


def test_subclass_validates_auth_type(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    assert p._auth.kind == "api_key"  # noqa: SLF001


def test_subclass_rejects_unsupported_auth():
    with pytest.raises(UnsupportedAuthError) as exc:
        _DummyProvider(auth=OAuth2CliToken(env_var="X"))
    assert exc.value.provider == "dummy"
    assert exc.value.got == "OAuth2CliToken"
    assert "ApiKey" in exc.value.accepted


def test_require_capability_passes_when_true(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    p.require_capability("mcp")  # supports_mcp=True


def test_require_capability_raises_when_false(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    with pytest.raises(UnsupportedCapabilityError) as exc:
        p.require_capability("hooks")
    assert exc.value.provider == "dummy"
    assert exc.value.capability == "hooks"


def test_translate_hooks_default_to_NotImplementedError(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    p = _DummyProvider(auth=ApiKey())
    with pytest.raises(NotImplementedError):
        p._translate_system_prompt(None)  # type: ignore[arg-type]  # noqa: SLF001
    with pytest.raises(NotImplementedError):
        p._translate_tools(None)  # type: ignore[arg-type]  # noqa: SLF001
    with pytest.raises(NotImplementedError):
        p._translate_mcp(())  # noqa: SLF001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_base.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.base'`

- [ ] **Step 3: Implement `BaseProvider`**

`src/llm_providers/base.py`:
```python
"""BaseProvider ABC + StatefulClient Protocol.

Subclasses declare three ClassVars (name, capabilities, supported_auth) and
implement query() and client(). Translation hooks default to NotImplementedError;
each subclass overrides the ones relevant to its capability set.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Protocol

from llm_providers.auth.base import AuthStrategy
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.prompt import SystemPrompt
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.tools import McpServerSpec, ToolPolicy


class StatefulClient(Protocol):
    """Multi-turn session counterpart to query(). Used by stateful providers."""
    async def __aenter__(self) -> "StatefulClient": ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def query(self, prompt: str) -> AsyncIterator[Message]: ...


class BaseProvider(ABC):
    """Vendor-neutral provider interface.

    Liskov contract:
      - Every subclass accepts the same ProviderOptions in query()/client().
      - Vendor specifics travel through ProviderOptions.extras[<provider name>].
      - Capability gaps are surfaced via UnsupportedCapabilityError, never
        silently ignored.
    """
    name: ClassVar[str]
    capabilities: ClassVar[Capabilities]
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]]

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

    def require_capability(self, name: str) -> None:
        """Raise UnsupportedCapabilityError if capabilities.supports_<name> is False."""
        flag = f"supports_{name}"
        if not getattr(self.capabilities, flag, False):
            raise UnsupportedCapabilityError(provider=self.name, capability=name)

    # ---- Required overrides --------------------------------------------------

    @abstractmethod
    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        """One-shot streaming query. Yields Messages; emits a final Message
        with is_final=True before the iterator ends."""
        ...

    @abstractmethod
    def client(self, options: ProviderOptions) -> StatefulClient:
        """Stateful multi-turn client. Raise UnsupportedCapabilityError if
        capabilities.supports_stateful_client is False."""
        ...

    # ---- Translation hooks ---------------------------------------------------
    # Subclasses override the ones relevant to their feature set. The base
    # raises NotImplementedError with a clear name so an over-eager caller
    # gets a precise error instead of a silent AttributeError.

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_system_prompt not implemented"
        )

    def _translate_tools(self, policy: ToolPolicy) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_tools not implemented"
        )

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_mcp not implemented"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_base.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/base.py tests/llm_providers/test_base.py
git commit -m "feat(llm_providers): BaseProvider ABC + StatefulClient Protocol"
```

---

## Task 9: `ProviderRegistry` + `AuthRegistry` + `auto_resolve_auth`

**Files:**
- Create: `src/llm_providers/registry.py`
- Create: `tests/llm_providers/test_registry.py`
- Create: `tests/llm_providers/test_auth_resolution.py`

- [ ] **Step 1: Write the failing tests**

`tests/llm_providers/test_registry.py`:
```python
"""Provider/Auth registry tests — register, get, build, build_auto, duplicates."""
import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.base import BaseProvider
from llm_providers.errors import ProviderNotFoundError, UnsupportedAuthError
from llm_providers.protocol import Capabilities
from llm_providers.registry import AuthRegistry, ProviderRegistry


@pytest.fixture(autouse=True)
def _isolate_registries(monkeypatch):
    """Each test gets a fresh empty registry to avoid cross-test pollution."""
    monkeypatch.setattr(ProviderRegistry, "_providers", {})
    monkeypatch.setattr(AuthRegistry, "_strategies", {})


def _caps() -> Capabilities:
    return Capabilities(
        supports_mcp=False, supports_native_tools=False, supports_hooks=False,
        supports_stateful_client=False, supports_output_schema=False,
        supports_system_prompt_file=False, supports_streaming=False,
    )


def _make_provider(name: str):
    @ProviderRegistry.register(name)
    class _P(BaseProvider):
        pass
    _P.name = name
    _P.capabilities = _caps()
    _P.supported_auth = (ApiKey,)

    async def _q(self, prompt, options):
        from llm_providers.protocol import Message
        yield Message(text="x", is_final=True)
    _P.query = _q
    _P.client = lambda self, options: None  # type: ignore[assignment]
    _P.__abstractmethods__ = frozenset()
    return _P


def test_register_and_get():
    cls = _make_provider("foo")
    assert ProviderRegistry.get("foo") is cls


def test_get_unknown_raises():
    with pytest.raises(ProviderNotFoundError) as exc:
        ProviderRegistry.get("nope")
    assert exc.value.name == "nope"


def test_register_rejects_duplicate():
    _make_provider("foo")
    with pytest.raises(ValueError, match="already registered"):
        _make_provider("foo")


def test_register_rejects_non_baseprovider():
    with pytest.raises(TypeError, match="BaseProvider"):
        @ProviderRegistry.register("nope")
        class _NotAProvider:
            pass


def test_register_rejects_name_mismatch():
    with pytest.raises(ValueError, match="!="):
        @ProviderRegistry.register("foo")
        class _P(BaseProvider):
            name = "bar"  # mismatch
            capabilities = _caps()
            supported_auth = (ApiKey,)
            async def query(self, p, o):
                from llm_providers.protocol import Message
                yield Message(text="", is_final=True)
            def client(self, o):
                return None


def test_build_constructs_with_auth(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _make_provider("foo")
    p = ProviderRegistry.build("foo", auth=ApiKey())
    assert p.name == "foo"


def test_build_rejects_wrong_auth():
    _make_provider("foo")
    class _Other(AuthStrategy):
        kind = "other"
        def detect(self) -> bool: return True
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls): return cls()
    with pytest.raises(UnsupportedAuthError):
        ProviderRegistry.build("foo", auth=_Other())


def test_names_returns_sorted_tuple():
    _make_provider("zeta")
    _make_provider("alpha")
    assert ProviderRegistry.names() == ("alpha", "zeta")


def test_auth_registry_register_and_kinds():
    @AuthRegistry.register("my-kind")
    class _S(AuthStrategy):
        kind = "my-kind"
        def detect(self) -> bool: return True
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls): return cls()
    assert AuthRegistry.get("my-kind") is _S
    assert "my-kind" in AuthRegistry.kinds()


def test_auth_registry_rejects_duplicate():
    @AuthRegistry.register("dup")
    class _A(AuthStrategy):
        kind = "dup"
        def detect(self) -> bool: return False
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls): return cls()
    with pytest.raises(ValueError, match="already registered"):
        @AuthRegistry.register("dup")
        class _B(AuthStrategy):  # noqa: F811
            kind = "dup"
            def detect(self) -> bool: return False
            def resolve(self) -> Credential:
                return Credential(kind=self.kind, payload={})
            @classmethod
            def default(cls): return cls()
```

`tests/llm_providers/test_auth_resolution.py`:
```python
"""auto_resolve_auth walk + accepted_kinds filter."""
import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider
from llm_providers.errors import AuthResolutionError
from llm_providers.protocol import Capabilities
from llm_providers.registry import ProviderRegistry, auto_resolve_auth


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    monkeypatch.setattr(ProviderRegistry, "_providers", {})


def _register_provider(name: str, supported_auth):
    @ProviderRegistry.register(name)
    class _P(BaseProvider):
        pass
    _P.name = name
    _P.capabilities = Capabilities(
        supports_mcp=False, supports_native_tools=False, supports_hooks=False,
        supports_stateful_client=False, supports_output_schema=False,
        supports_system_prompt_file=False, supports_streaming=False,
    )
    _P.supported_auth = supported_auth
    async def _q(self, p, o):
        from llm_providers.protocol import Message
        yield Message(text="", is_final=True)
    _P.query = _q
    _P.client = lambda self, o: None  # type: ignore[assignment]
    _P.__abstractmethods__ = frozenset()
    return _P


def test_walks_preferred_first_returns_first_detected(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDERS_API_KEY", raising=False)
    monkeypatch.setenv("TOK", "tok-xyz")
    class _PreferredOAuth(OAuth2CliToken):
        @classmethod
        def default(cls): return cls(env_var="TOK")
    _register_provider("foo", (_PreferredOAuth, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "oauth2_cli_token"


def test_falls_through_to_second_when_first_not_detected(monkeypatch):
    # Neither OAuth2CliToken default nor API key is wired; use a custom subclass
    class _OAuthNever(OAuth2CliToken):
        @classmethod
        def default(cls): return cls()  # no env_var, no path → never detects
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (_OAuthNever, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "api_key"


def test_accepted_kinds_filters_out_strategies(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (ApiKey,))
    with pytest.raises(AuthResolutionError) as exc:
        auto_resolve_auth("foo", accepted_kinds={"oauth2_cli_token"})
    skipped_names = {name for name, _reason in exc.value.skipped}
    assert "ApiKey" in skipped_names
    assert any("filtered" in reason for _name, reason in exc.value.skipped)


def test_raises_when_no_strategy_detects(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDERS_API_KEY", raising=False)
    _register_provider("foo", (ApiKey,))
    with pytest.raises(AuthResolutionError) as exc:
        auto_resolve_auth("foo")
    assert exc.value.provider == "foo"
    assert any("not_detected" in reason for _name, reason in exc.value.skipped)


def test_construct_failure_is_skipped_not_raised(monkeypatch):
    class _Broken(AuthStrategy):
        kind = "broken"
        def detect(self) -> bool: return True
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls):
            raise RuntimeError("construct failed")
    monkeypatch.setenv("LLM_PROVIDERS_API_KEY", "k")
    _register_provider("foo", (_Broken, ApiKey))
    result = auto_resolve_auth("foo")
    assert result.kind == "api_key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/llm_providers/test_registry.py tests/llm_providers/test_auth_resolution.py -v`
Expected: `ModuleNotFoundError: No module named 'llm_providers.registry'`

- [ ] **Step 3: Implement `registry.py`**

`src/llm_providers/registry.py`:
```python
"""ProviderRegistry, AuthRegistry, and auto_resolve_auth.

Decorator-based registries: subclasses self-register at class definition time
via @ProviderRegistry.register("name") and @AuthRegistry.register("kind").
Open for extension (one decorator), closed for modification (no edits to
registry.py to add a provider).
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import ClassVar

from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import AuthResolutionError, ProviderNotFoundError

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of BaseProvider subclasses keyed by their `name` ClassVar."""
    _providers: ClassVar[dict[str, type[BaseProvider]]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[BaseProvider]], type[BaseProvider]]:
        def decorator(provider_cls: type[BaseProvider]) -> type[BaseProvider]:
            if not issubclass(provider_cls, BaseProvider):
                raise TypeError(
                    f"{provider_cls.__name__} must subclass BaseProvider to be "
                    "registered."
                )
            if name in cls._providers:
                raise ValueError(
                    f"Provider {name!r} is already registered by "
                    f"{cls._providers[name].__name__}; refusing to overwrite."
                )
            declared = getattr(provider_cls, "name", None)
            if declared != name:
                raise ValueError(
                    f"Decorator name={name!r} != class.name={declared!r}. "
                    "Both sources of truth must match."
                )
            cls._providers[name] = provider_cls
            logger.debug("Registered provider %r → %s", name, provider_cls.__name__)
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseProvider]:
        try:
            return cls._providers[name]
        except KeyError:
            raise ProviderNotFoundError(
                name=name, available=tuple(sorted(cls._providers))
            ) from None

    @classmethod
    def build(cls, name: str, *, auth: AuthStrategy) -> BaseProvider:
        return cls.get(name)(auth=auth)

    @classmethod
    def build_auto(
        cls,
        name: str,
        *,
        accepted_kinds: Iterable[str] | None = None,
    ) -> BaseProvider:
        provider_cls = cls.get(name)
        auth = auto_resolve_auth(name, accepted_kinds=accepted_kinds)
        return provider_cls(auth=auth)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._providers))


class AuthRegistry:
    """Registry of AuthStrategy subclasses keyed by their `kind` ClassVar."""
    _strategies: ClassVar[dict[str, type[AuthStrategy]]] = {}

    @classmethod
    def register(cls, kind: str) -> Callable[[type[AuthStrategy]], type[AuthStrategy]]:
        def decorator(strat_cls: type[AuthStrategy]) -> type[AuthStrategy]:
            if not issubclass(strat_cls, AuthStrategy):
                raise TypeError(
                    f"{strat_cls.__name__} must subclass AuthStrategy to be "
                    "registered."
                )
            if kind in cls._strategies:
                raise ValueError(
                    f"AuthStrategy {kind!r} is already registered by "
                    f"{cls._strategies[kind].__name__}; refusing to overwrite."
                )
            declared = getattr(strat_cls, "kind", None)
            if declared != kind:
                raise ValueError(
                    f"Decorator kind={kind!r} != class.kind={declared!r}. "
                    "Both sources of truth must match."
                )
            cls._strategies[kind] = strat_cls
            logger.debug("Registered auth strategy %r → %s", kind, strat_cls.__name__)
            return strat_cls
        return decorator

    @classmethod
    def get(cls, kind: str) -> type[AuthStrategy]:
        try:
            return cls._strategies[kind]
        except KeyError:
            raise KeyError(
                f"AuthStrategy {kind!r} not registered. Available: "
                f"{tuple(sorted(cls._strategies))}."
            ) from None

    @classmethod
    def kinds(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._strategies))


def auto_resolve_auth(
    provider_name: str,
    *,
    accepted_kinds: Iterable[str] | None = None,
) -> AuthStrategy:
    """Walk provider.supported_auth in declared (preferred-first) order.

    For each candidate strategy:
      1. If accepted_kinds is provided and strategy.kind is not in it → skip.
      2. Try strategy.default() — if it raises, record and skip.
      3. If instance.detect() returns False, record and skip.
      4. Otherwise return the instance.

    Raises AuthResolutionError if no strategy resolves; the error lists every
    strategy tried and why it was skipped.
    """
    provider_cls = ProviderRegistry.get(provider_name)
    accepted = set(accepted_kinds) if accepted_kinds is not None else None
    skipped: list[tuple[str, str]] = []

    for strat_cls in provider_cls.supported_auth:
        if accepted is not None and strat_cls.kind not in accepted:
            skipped.append((strat_cls.__name__, "filtered_by_accepted_kinds"))
            continue
        try:
            instance = strat_cls.default()
        except Exception as e:  # noqa: BLE001 — strategy owns its construction errors
            skipped.append((strat_cls.__name__, f"construct_failed: {e}"))
            continue
        if instance.detect():
            return instance
        skipped.append((strat_cls.__name__, "not_detected"))

    raise AuthResolutionError(
        provider=provider_name, skipped=skipped, accepted=accepted
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/llm_providers/test_registry.py tests/llm_providers/test_auth_resolution.py -v`
Expected: all passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/registry.py tests/llm_providers/test_registry.py \
        tests/llm_providers/test_auth_resolution.py
git commit -m "feat(llm_providers): ProviderRegistry, AuthRegistry, auto_resolve_auth"
```

---

## Task 10: Codex config parser (`_codex_config.py`)

This ports the existing `hsb.runtime.codex_guards` into the library so OpenAIProvider's Codex backend has no dependency on hsb.

**Files:**
- Create: `src/llm_providers/providers/__init__.py` (empty for now; populated in Task 13)
- Create: `src/llm_providers/providers/_codex_config.py`
- Create: `tests/llm_providers/providers/__init__.py`
- Create: `tests/llm_providers/providers/test_codex_config.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/providers/test_codex_config.py`:
```python
"""Codex ~/.codex/config.toml parsing + OAuth-only verification.

Ported from tests/runtime/test_codex_guards.py — once Task 16 lands, that
file becomes a re-export shim and these become the canonical tests.
"""
from pathlib import Path

import pytest

from llm_providers.providers._codex_config import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)


def _write_config(home: Path, body: str) -> None:
    (home / "config.toml").write_text(body)


def _write_auth(home: Path) -> None:
    (home / "auth.json").write_text('{"access_token": "x"}')


def test_missing_config_raises(tmp_path):
    with pytest.raises(RuntimeError, match="config.toml not found"):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_missing_forced_login_raises(tmp_path):
    _write_config(tmp_path, "")
    _write_auth(tmp_path)
    with pytest.raises(RuntimeError, match='forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_wrong_forced_login_raises(tmp_path):
    _write_config(tmp_path, 'forced_login_method = "apikey"')
    _write_auth(tmp_path)
    with pytest.raises(RuntimeError, match='forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_missing_auth_json_raises(tmp_path):
    _write_config(tmp_path, 'forced_login_method = "chatgpt"')
    with pytest.raises(RuntimeError, match="auth.json"):
        assert_codex_oauth_only(codex_home=tmp_path)


def test_valid_config_returns_parsed(tmp_path):
    _write_config(tmp_path, 'forced_login_method = "chatgpt"\n[mcp_servers.linear]\nurl = "x"')
    _write_auth(tmp_path)
    parsed = assert_codex_oauth_only(codex_home=tmp_path)
    assert parsed["forced_login_method"] == "chatgpt"
    assert "linear" in parsed["mcp_servers"]


def test_verify_codex_mcp_ok():
    parsed = {"mcp_servers": {"linear": {}, "filesystem": {}}}
    verify_codex_mcp(parsed, ["linear"])  # no raise


def test_verify_codex_mcp_missing_raises():
    parsed = {"mcp_servers": {"linear": {}}}
    with pytest.raises(RuntimeError, match="filesystem"):
        verify_codex_mcp(parsed, ["filesystem"])


def test_resolve_codex_home_from_env(monkeypatch, tmp_path):
    """Internal helper honors CODEX_HOME env var."""
    from llm_providers.providers._codex_config import _resolve_codex_home
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert _resolve_codex_home() == tmp_path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/providers/test_codex_config.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Port the guard logic**

`src/llm_providers/providers/_codex_config.py`:
```python
"""Codex CLI configuration parsing — ports hsb.runtime.codex_guards into
the library so OpenAIProvider's Codex backend has no dependency on hsb.

Two helpers:
  - assert_codex_oauth_only(codex_home=None): init-time. Verifies
    ~/.codex/config.toml has `forced_login_method = "chatgpt"` and
    ~/.codex/auth.json exists. Returns the parsed config so the caller
    can cache it.
  - verify_codex_mcp(parsed_config, requested_servers): per-call check.
    For each requested MCP server name, asserts a [mcp_servers.<name>]
    block exists in the parsed config.
"""
from __future__ import annotations

import os
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def _resolve_codex_home(codex_home: Path | None = None) -> Path:
    if codex_home is not None:
        return codex_home
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codex"


def assert_codex_oauth_only(codex_home: Path | None = None) -> dict[str, Any]:
    """Init-time check. Returns the parsed config.toml dict.

    Caller should cache the return value and pass it to verify_codex_mcp on
    each query() call to avoid re-reading the file.
    """
    home = _resolve_codex_home(codex_home)
    config_path = home / "config.toml"
    auth_path = home / "auth.json"

    if not config_path.exists():
        raise RuntimeError(
            f"Codex config.toml not found at {config_path}. "
            'Codex CLI must be configured with forced_login_method = "chatgpt". '
            "See https://platform.openai.com/docs/codex for setup."
        )
    parsed = tomllib.loads(config_path.read_text())

    if parsed.get("forced_login_method") != "chatgpt":
        raise RuntimeError(
            f"Codex forced_login_method must be \"chatgpt\" in {config_path} "
            f"(got {parsed.get('forced_login_method')!r}). OAuth-only "
            "enforcement: API-key auth disallowed by this strategy."
        )

    if not auth_path.exists():
        raise RuntimeError(
            f"Codex not authenticated: {auth_path} missing. "
            "Run: codex login --device-auth"
        )

    return parsed


def verify_codex_mcp(parsed_config: dict, requested_servers: Iterable[str]) -> None:
    """Per-call cheap dict lookup against cached parsed config."""
    available = (parsed_config.get("mcp_servers") or {}).keys()
    missing = [s for s in requested_servers if s not in available]
    if missing:
        raise RuntimeError(
            f"Codex MCP missing: [mcp_servers.{', mcp_servers.'.join(missing)}] "
            f"block(s) not found in Codex config.toml."
        )
```

`src/llm_providers/providers/__init__.py`: empty file (populated in Task 13).

`tests/llm_providers/providers/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/providers/test_codex_config.py -v`
Expected: 8 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/providers/__init__.py \
        src/llm_providers/providers/_codex_config.py \
        tests/llm_providers/providers/__init__.py \
        tests/llm_providers/providers/test_codex_config.py
git commit -m "feat(llm_providers): port Codex config parser into library"
```

---

## Task 11: `ClaudeProvider`

**Files:**
- Create: `src/llm_providers/providers/claude.py`
- Create: `tests/llm_providers/providers/test_claude.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/providers/test_claude.py`:
```python
"""ClaudeProvider — translation hooks + auth wiring with mocked SDK."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    TextSystemPrompt,
)
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.tools import McpServerSpec, ToolPolicy


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
        yield ClaudeProvider(
            auth=OAuth2CliToken(env_var="CLAUDE_CODE_OAUTH_TOKEN")
        )


def test_capabilities_declared():
    with patch.dict("sys.modules", {
        "claude_agent_sdk": SimpleNamespace(
            ClaudeAgentOptions=MagicMock(), ClaudeSDKClient=MagicMock(),
            query=MagicMock(),
            AssistantMessage=type("X", (), {}), ResultMessage=type("Y", (), {}),
        )
    }):
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
    with patch.dict("sys.modules", {
        "claude_agent_sdk": SimpleNamespace(
            ClaudeAgentOptions=MagicMock(), ClaudeSDKClient=MagicMock(),
            query=MagicMock(),
            AssistantMessage=type("X", (), {}), ResultMessage=type("Y", (), {}),
        )
    }):
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
        def detect(self) -> bool: return True
        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})
        @classmethod
        def default(cls): return cls()
    with patch.dict("sys.modules", {
        "claude_agent_sdk": SimpleNamespace(
            ClaudeAgentOptions=MagicMock(), ClaudeSDKClient=MagicMock(),
            query=MagicMock(),
            AssistantMessage=type("X", (), {}), ResultMessage=type("Y", (), {}),
        )
    }):
        from llm_providers.providers.claude import ClaudeProvider
        with pytest.raises(UnsupportedAuthError):
            ClaudeProvider(auth=_Other())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/providers/test_claude.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `ClaudeProvider`**

`src/llm_providers/providers/claude.py`:
```python
"""ClaudeProvider — wraps claude_agent_sdk."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import ProviderRuntimeError, TranslationError
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


@ProviderRegistry.register("claude")
class ClaudeProvider(BaseProvider):
    """Native Claude provider using claude_agent_sdk.

    Recognized ProviderOptions.extras["claude"] keys:
      - "hooks": list of HookMatcher instances (Claude-only).
    """
    name: ClassVar[str] = "claude"
    capabilities: ClassVar[Capabilities] = Capabilities(
        supports_mcp=True,
        supports_native_tools=True,
        supports_hooks=True,
        supports_stateful_client=True,
        supports_output_schema=True,
        supports_system_prompt_file=True,
        supports_streaming=True,
    )
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (OAuth2CliToken, ApiKey)

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        import claude_agent_sdk
        self._sdk = claude_agent_sdk
        self._apply_credential()

    def _apply_credential(self) -> None:
        """Inject the resolved credential into the env var the SDK reads."""
        import os
        cred = self._auth.resolve()
        if cred.kind == "oauth2_cli_token":
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = cred.payload["token"]
        elif cred.kind == "api_key":
            os.environ["ANTHROPIC_API_KEY"] = cred.payload["api_key"]

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        sdk_options = self._build_native_options(options)
        try:
            async for sdk_msg in self._sdk.query(prompt=prompt, options=sdk_options):
                yield self._to_message(sdk_msg)
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="query") from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        sdk_options = self._build_native_options(options)
        try:
            sdk_client = self._sdk.ClaudeSDKClient(options=sdk_options)
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="client_init") from e
        return _ClaudeStatefulClient(sdk_client)

    # ---- Translation hooks ---------------------------------------------------

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            # Claude has SystemPromptFile, but for portability we read the file
            # contents and pass as a plain string. (A future enhancement can
            # detect SystemPromptFile availability on the SDK and prefer it.)
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            # Claude supports presets via SystemPromptPreset; return the id and
            # let the build step wrap it. For our purposes we expose the id
            # as a dict with a marker so _build_native_options can recognize it.
            return {"__preset_id__": sp.preset_id}
        raise TranslationError(f"Unknown SystemPrompt subtype: {type(sp).__name__}")

    def _translate_tools(self, policy: ToolPolicy) -> dict:
        # Pass-through to claude_agent_sdk's allowed_tools.
        return {
            "allowed_tools": list(policy.allowed),
            # Custom tools live in extras["claude"]["custom_mcp"] if a caller
            # wants to wire in @tool-decorated handlers. Phase A keeps the
            # pass-through minimal; richer wiring lands when a caller needs it.
        }

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> dict:
        out: dict[str, dict] = {}
        for s in servers:
            entry: dict[str, Any] = {"transport": s.transport}
            if s.command is not None:
                entry["command"] = list(s.command)
            if s.url is not None:
                entry["url"] = s.url
            if s.env:
                entry["env"] = dict(s.env)
            out[s.name] = entry
        return out

    # ---- Helpers -------------------------------------------------------------

    def _build_native_options(self, options: ProviderOptions) -> Any:
        sp = self._translate_system_prompt(options.system_prompt)
        tools = self._translate_tools(options.tool_policy)
        mcp = self._translate_mcp(options.mcp_servers) if options.mcp_servers else None
        kwargs: dict[str, Any] = {
            "system_prompt": sp,
            "allowed_tools": tools["allowed_tools"],
            "permission_mode": options.permission_mode,
            "max_turns": options.max_turns,
            "model": options.model,
        }
        if mcp is not None:
            kwargs["mcp_servers"] = mcp
        if options.cwd is not None:
            kwargs["cwd"] = options.cwd
        extras = options.extras.get(self.name, {}) if options.extras else {}
        if "hooks" in extras:
            kwargs["hooks"] = extras["hooks"]
        return self._sdk.ClaudeAgentOptions(**kwargs)

    def _to_message(self, sdk_msg: Any) -> Message:
        if isinstance(sdk_msg, self._sdk.ResultMessage):
            return Message(text="", is_final=True, raw=sdk_msg)
        if isinstance(sdk_msg, self._sdk.AssistantMessage):
            text = "".join(getattr(b, "text", "") for b in (sdk_msg.content or []))
            return Message(text=text, is_final=False, raw=sdk_msg)
        return Message(text="", is_final=False, raw=sdk_msg)


class _ClaudeStatefulClient:
    """Adapter from claude_agent_sdk.ClaudeSDKClient to StatefulClient Protocol."""
    def __init__(self, sdk_client: Any) -> None:
        self._inner = sdk_client

    async def __aenter__(self) -> "_ClaudeStatefulClient":
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._inner.__aexit__(*exc)

    async def query(self, prompt: str) -> AsyncIterator[Message]:
        async for sdk_msg in self._inner.query(prompt):
            yield Message(text="", is_final=False, raw=sdk_msg)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/providers/test_claude.py -v`
Expected: all passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/providers/claude.py tests/llm_providers/providers/test_claude.py
git commit -m "feat(llm_providers): ClaudeProvider (claude-agent-sdk wrapper)"
```

---

## Task 12: `OpenAIProvider` (dual-backend)

**Files:**
- Create: `src/llm_providers/providers/openai.py`
- Create: `tests/llm_providers/providers/test_openai.py`

- [ ] **Step 1: Write the failing test**

`tests/llm_providers/providers/test_openai.py`:
```python
"""OpenAIProvider — dual-backend routing (Codex CLI vs raw OpenAI)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken


def _stub_codex_sdk():
    return SimpleNamespace(
        Codex=MagicMock(),
        TextInput=MagicMock(),
        ThreadOptions=MagicMock(),
        TurnOptions=MagicMock(),
        TurnCompletedEvent=type("TurnCompletedEvent", (), {}),
        TurnFailedEvent=type("TurnFailedEvent", (), {}),
        types=SimpleNamespace(CodexOptions=MagicMock()),
    )


def _stub_openai_sdk():
    return SimpleNamespace(OpenAI=MagicMock())


def test_codex_backend_selected_for_oauth_token(monkeypatch, tmp_path):
    # Set up a valid Codex config so the backend init guard passes.
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _CodexBackend
        p = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert isinstance(p._backend, _CodexBackend)


def test_raw_openai_backend_selected_for_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
    sdks = {"openai": _stub_openai_sdk()}
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider, _RawOpenAIBackend
        p = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert isinstance(p._backend, _RawOpenAIBackend)


def test_capabilities_differ_by_backend(monkeypatch, tmp_path):
    """supports_mcp is True only on the Codex backend."""
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk")

    sdks_codex = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    sdks_raw = {"openai": _stub_openai_sdk()}

    with patch.dict("sys.modules", sdks_codex):
        from llm_providers.providers.openai import OpenAIProvider
        p_codex = OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
        assert p_codex.capabilities.supports_mcp is True

    with patch.dict("sys.modules", sdks_raw):
        # Re-import via module reload would be needed if classes were cached;
        # OpenAIProvider doesn't cache, so a new instance picks the raw backend.
        p_raw = OpenAIProvider(auth=ApiKey(env_var="OPENAI_API_KEY"))
        assert p_raw.capabilities.supports_mcp is False


def test_supported_auth():
    from llm_providers.providers.openai import OpenAIProvider
    assert OAuth2CliToken in OpenAIProvider.supported_auth
    assert ApiKey in OpenAIProvider.supported_auth


def test_codex_backend_init_calls_oauth_guard(monkeypatch, tmp_path):
    """The Codex backend must verify ~/.codex/config.toml at init."""
    # No config.toml → guard should raise.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    sdks = {
        "openai_codex_sdk": _stub_codex_sdk(),
        "openai_codex_sdk.types": _stub_codex_sdk().types,
    }
    with patch.dict("sys.modules", sdks):
        from llm_providers.providers.openai import OpenAIProvider
        with pytest.raises(RuntimeError, match="config.toml not found"):
            OpenAIProvider(auth=OAuth2CliToken(token_path=tmp_path / "auth.json"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/providers/test_openai.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `OpenAIProvider` with dual backends**

`src/llm_providers/providers/openai.py`:
```python
"""OpenAIProvider — single provider, two internal backends.

  - _CodexBackend: openai_codex_sdk. Operator's ChatGPT subscription quota.
                   Selected when auth resolves to oauth2_cli_token kind.
  - _RawOpenAIBackend: openai SDK. Metered api.openai.com.
                       Selected when auth resolves to api_key kind.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import (
    CredentialMismatch,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedCapabilityError,
)
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import Capabilities, Message, PermissionMode, ProviderOptions
from llm_providers.providers._codex_config import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)
from llm_providers.registry import ProviderRegistry
from llm_providers.tools import McpServerSpec, ToolPolicy


_CODEX_CAPS = Capabilities(
    supports_mcp=True,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=True,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)

_RAW_CAPS = Capabilities(
    supports_mcp=False,
    supports_native_tools=True,
    supports_hooks=False,
    supports_stateful_client=True,
    supports_output_schema=True,
    supports_system_prompt_file=False,
    supports_streaming=True,
)


_PERMISSION_MAP: dict[PermissionMode, str] = {
    "default": "on-request",
    "acceptEdits": "never",
    "plan": "on-request",
    "bypassPermissions": "never",
}


@ProviderRegistry.register("openai")
class OpenAIProvider(BaseProvider):
    """OpenAI provider with two internal backends selected by auth kind.

    Recognized ProviderOptions.extras["openai"] keys: none in Phase A.
    """
    name: ClassVar[str] = "openai"
    # Class-level placeholder; overridden by instance property below.
    capabilities: ClassVar[Capabilities] = _RAW_CAPS  # type: ignore[assignment]
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]] = (OAuth2CliToken, ApiKey)

    def __init__(self, auth: AuthStrategy) -> None:
        super().__init__(auth)
        cred = self._auth.resolve()
        if cred.kind == "oauth2_cli_token":
            self._backend: _Backend = _CodexBackend(cred)
        elif cred.kind == "api_key":
            self._backend = _RawOpenAIBackend(cred)
        else:
            raise CredentialMismatch(
                f"OpenAIProvider cannot apply credential kind {cred.kind!r}"
            )

    @property  # type: ignore[override]
    def capabilities(self) -> Capabilities:  # noqa: F811
        return self._backend.capabilities

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        try:
            async for msg in self._backend.query(prompt, options, self):
                yield msg
        except ProviderRuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=self.name, phase="query") from e

    def client(self, options: ProviderOptions) -> StatefulClient:
        return self._backend.client(options, self)

    # ---- Translation hooks (shared across backends) --------------------------

    def _translate_system_prompt(self, sp: SystemPrompt) -> str:
        if isinstance(sp, TextSystemPrompt):
            return sp.text
        if isinstance(sp, SkillReference):
            return sp.path.read_text(encoding="utf-8")
        if isinstance(sp, PresetSystemPrompt):
            raise UnsupportedCapabilityError(
                provider=self.name, capability="system_prompt_file"
            )
        raise TranslationError(f"Unknown SystemPrompt subtype: {type(sp).__name__}")

    def _translate_tools(self, policy: ToolPolicy) -> dict:
        return {"allowed_tools": list(policy.allowed)}

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> dict:
        # Backend decides whether MCP is supported. Codex verifies operator
        # config; raw OpenAI raises UnsupportedCapabilityError.
        return self._backend.translate_mcp(servers, self)


class _Backend:
    """Common backend interface — shared shape; implementations differ."""
    capabilities: Capabilities

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        raise NotImplementedError

    def client(self, options: ProviderOptions, provider: OpenAIProvider) -> StatefulClient:
        raise NotImplementedError

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> Any:
        raise NotImplementedError


class _CodexBackend(_Backend):
    """openai_codex_sdk backend. OAuth-only; verifies operator's ~/.codex config."""
    capabilities = _CODEX_CAPS

    def __init__(self, cred: Credential) -> None:
        # cred.payload["source"] is "env:..." or "file:<path>" — for "file:" we
        # derive codex_home from the file's parent for the config verification.
        source = cred.payload.get("source", "")
        codex_home: Path | None = None
        if source.startswith("file:"):
            codex_home = Path(source.removeprefix("file:")).parent
        self._cached_config = assert_codex_oauth_only(codex_home=codex_home)
        import openai_codex_sdk
        self._sdk = openai_codex_sdk
        self._codex_home = codex_home

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        if options.mcp_servers:
            verify_codex_mcp(self._cached_config, [s.name for s in options.mcp_servers])

        approval = _PERMISSION_MAP.get(options.permission_mode)
        if approval is None:
            raise UnsupportedCapabilityError(
                provider=provider.name,
                capability=f"permission_mode={options.permission_mode}",
            )

        sp_text = provider._translate_system_prompt(options.system_prompt)
        full_text = f"<system>{sp_text}</system>\n\n{prompt}"

        thread_options = self._sdk.ThreadOptions(
            model=options.model,
            approvalPolicy=approval,
            workingDirectory=options.cwd,
        )
        turn_options = self._sdk.TurnOptions(outputSchema=options.output_schema)

        codex_opts = self._build_codex_options()
        codex = self._sdk.Codex(codex_opts) if codex_opts is not None else self._sdk.Codex()
        thread = codex.start_thread(thread_options)
        streamed = await thread.run_streamed(
            self._sdk.TextInput(type="text", text=full_text),
            turn_options,
        )

        turns_seen = 0
        final_buffer: list[str] = []
        async for evt in streamed.events:
            if isinstance(evt, self._sdk.TurnCompletedEvent | self._sdk.TurnFailedEvent):
                turns_seen += 1
                if turns_seen > options.max_turns:
                    raise RuntimeError(
                        f"Codex exceeded max_turns={options.max_turns}; aborting."
                    )
            evt_text = self._extract_event_text(evt)
            if evt_text:
                final_buffer.append(evt_text)
            yield Message(text=evt_text, is_final=False, raw=evt)

        yield Message(text="".join(final_buffer), is_final=True, raw=None)

    def client(self, options: ProviderOptions, provider: OpenAIProvider) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (Codex backend: not wired in Phase A)",
        )

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> dict[str, dict]:
        # Codex MCP is operator-managed in ~/.codex/config.toml. We verify the
        # requested names are present and return the resolved blocks for
        # visibility; we do NOT write to the operator's config.
        verify_codex_mcp(self._cached_config, [s.name for s in servers])
        return {
            s.name: self._cached_config["mcp_servers"][s.name] for s in servers
        }

    @staticmethod
    def _extract_event_text(evt: Any) -> str:
        direct = getattr(evt, "text", None)
        if isinstance(direct, str) and direct:
            return direct
        item = getattr(evt, "item", None)
        if item is not None:
            item_text = getattr(item, "text", None)
            if isinstance(item_text, str) and item_text:
                return item_text
        return ""

    def _build_codex_options(self) -> Any:
        from openai_codex_sdk.types import CodexOptions
        override = os.environ.get("CODEX_PATH_OVERRIDE")
        if override:
            return CodexOptions(codex_path_override=override)
        return None


class _RawOpenAIBackend(_Backend):
    """openai SDK backend. API-key-based; no MCP support."""
    capabilities = _RAW_CAPS

    def __init__(self, cred: Credential) -> None:
        import openai
        self._sdk = openai
        self._client = openai.OpenAI(api_key=cred.payload["api_key"])

    async def query(
        self, prompt: str, options: ProviderOptions, provider: OpenAIProvider
    ) -> AsyncIterator[Message]:
        sp_text = provider._translate_system_prompt(options.system_prompt)
        messages = [
            {"role": "system", "content": sp_text},
            {"role": "user", "content": prompt},
        ]
        try:
            stream = await self._client.chat.completions.create(
                model=options.model,
                messages=messages,
                stream=True,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderRuntimeError(provider=provider.name, phase="query") from e

        final_buffer: list[str] = []
        async for chunk in stream:
            chunk_text = ""
            for choice in chunk.choices:
                delta = getattr(choice, "delta", None)
                if delta is not None:
                    chunk_text += getattr(delta, "content", "") or ""
            if chunk_text:
                final_buffer.append(chunk_text)
            yield Message(text=chunk_text, is_final=False, raw=chunk)
        yield Message(text="".join(final_buffer), is_final=True, raw=None)

    def client(self, options: ProviderOptions, provider: OpenAIProvider) -> StatefulClient:
        raise UnsupportedCapabilityError(
            provider=provider.name,
            capability="stateful_client (raw OpenAI backend: not wired in Phase A)",
        )

    def translate_mcp(
        self, servers: tuple[McpServerSpec, ...], provider: OpenAIProvider
    ) -> Any:
        if servers:
            raise UnsupportedCapabilityError(provider=provider.name, capability="mcp")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/providers/test_openai.py -v`
Expected: all passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/providers/openai.py tests/llm_providers/providers/test_openai.py
git commit -m "feat(llm_providers): OpenAIProvider dual-backend (Codex CLI + raw API)"
```

---

## Task 13: Wire side-effect imports

**Files:**
- Modify: `src/llm_providers/providers/__init__.py`
- Modify: `src/llm_providers/__init__.py`

- [ ] **Step 1: Write the failing test**

Add a new test file `tests/llm_providers/test_registration_side_effects.py`:
```python
"""Side-effect imports populate ProviderRegistry on package import."""
import importlib

import pytest


def test_provider_registry_populated_after_import_llm_providers(monkeypatch):
    # Reset registry to simulate cold start.
    from llm_providers.registry import ProviderRegistry
    monkeypatch.setattr(ProviderRegistry, "_providers", {})

    # Re-import the package to trigger side-effect registration.
    import llm_providers  # noqa: F401
    importlib.reload(llm_providers)

    names = ProviderRegistry.names()
    assert "claude" in names
    assert "openai" in names


def test_public_surface_re_exports():
    import llm_providers
    for name in [
        "Capabilities", "Message", "ProviderOptions",
        "ProviderRegistry", "AuthRegistry", "auto_resolve_auth",
        "ApiKey", "OAuth2CliToken",
        "TextSystemPrompt", "SkillReference", "PresetSystemPrompt",
        "LLMProvidersError", "UnsupportedCapabilityError",
        "UnsupportedAuthError", "AuthResolutionError", "ProviderNotFoundError",
    ]:
        assert hasattr(llm_providers, name), f"llm_providers.{name} missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm_providers/test_registration_side_effects.py -v`
Expected: `assert "claude" in names` fails — registry still empty after import.

- [ ] **Step 3: Implement side-effect imports**

`src/llm_providers/providers/__init__.py`:
```python
"""Importing this package triggers provider registration as a side effect.

Each module's class body runs @ProviderRegistry.register(...), populating
ProviderRegistry._providers. Order doesn't matter.
"""
from llm_providers.providers import claude  # noqa: F401
from llm_providers.providers import openai  # noqa: F401
```

`src/llm_providers/__init__.py` (full replacement):
```python
"""llm_providers — decoupled multi-provider LLM library.

Public surface re-exported below. Importing this package also triggers
provider and auth-strategy registration as a side effect.
"""
# Side-effect imports — must come before public-surface re-exports so the
# registries are populated when downstream code reads them.
from llm_providers import auth  # noqa: F401  (registers strategies if any)
from llm_providers import providers  # noqa: F401  (registers Claude + OpenAI)

from llm_providers.auth import ApiKey, AuthStrategy, Credential, OAuth2CliToken
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import (
    AuthDetectionFailed,
    AuthResolutionError,
    CredentialMismatch,
    LLMProvidersError,
    ProviderNotFoundError,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedAuthError,
    UnsupportedCapabilityError,
)
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)
from llm_providers.registry import (
    AuthRegistry,
    ProviderRegistry,
    auto_resolve_auth,
)
from llm_providers.tools import McpServerSpec, ToolPolicy, ToolSpec

__all__ = [
    # Auth
    "ApiKey", "AuthStrategy", "Credential", "OAuth2CliToken",
    # Base
    "BaseProvider", "StatefulClient",
    # Errors
    "AuthDetectionFailed", "AuthResolutionError", "CredentialMismatch",
    "LLMProvidersError", "ProviderNotFoundError", "ProviderRuntimeError",
    "TranslationError", "UnsupportedAuthError", "UnsupportedCapabilityError",
    # Prompt
    "PresetSystemPrompt", "SkillReference", "SystemPrompt", "TextSystemPrompt",
    # Protocol
    "Capabilities", "Message", "PermissionMode", "ProviderOptions",
    # Registry
    "AuthRegistry", "ProviderRegistry", "auto_resolve_auth",
    # Tools
    "McpServerSpec", "ToolPolicy", "ToolSpec",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_registration_side_effects.py -v`
Expected: 2 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/llm_providers tests/llm_providers && mypy src/llm_providers
git add src/llm_providers/__init__.py src/llm_providers/providers/__init__.py \
        tests/llm_providers/test_registration_side_effects.py
git commit -m "feat(llm_providers): wire side-effect imports for registration"
```

---

## Task 14: Conformance test suite

**Files:**
- Create: `tests/llm_providers/test_conformance.py`

- [ ] **Step 1: Write the test file**

`tests/llm_providers/test_conformance.py`:
```python
"""Conformance suite — parametrized over every registered provider.

Asserts the Liskov contract: every provider satisfies the same minimal
shape, and providers do not import from hsb (decoupling invariant).
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.protocol import Capabilities
from llm_providers.registry import ProviderRegistry


@pytest.fixture(scope="module")
def provider_names() -> list[str]:
    """All registered providers — populated by the side-effect imports."""
    import llm_providers  # noqa: F401  (ensure registration happens)
    return list(ProviderRegistry.names())


@pytest.fixture
def provider_cls(request):
    """Resolve a provider class by parametrized name."""
    return ProviderRegistry.get(request.param)


@pytest.mark.parametrize("name", ["claude", "openai"])
class TestProviderConformance:
    """Run the same assertions against every registered provider."""

    def test_subclasses_base_provider(self, name):
        cls = ProviderRegistry.get(name)
        assert issubclass(cls, BaseProvider)

    def test_name_classvar_matches_registry_key(self, name):
        cls = ProviderRegistry.get(name)
        assert cls.name == name

    def test_capabilities_is_a_Capabilities_instance(self, name):
        cls = ProviderRegistry.get(name)
        # capabilities may be ClassVar OR an instance property — both forms
        # are valid (see spec §7.2 note). The conformance test reads
        # capabilities off the class; if a provider uses @property the
        # ClassVar still has the default placeholder, which is fine.
        caps = getattr(cls, "capabilities", None)
        assert caps is not None
        # When it's a property descriptor, instantiating is needed; we assert
        # the type either way via duck-typing on the bool flags.
        if isinstance(caps, Capabilities):
            assert isinstance(caps.supports_mcp, bool)
        else:
            # It's a property — accept it; capability access happens on
            # instances. Conformance for instance capabilities is covered by
            # provider-specific tests.
            assert isinstance(caps, property)

    def test_supported_auth_is_nonempty_tuple_of_AuthStrategy(self, name):
        cls = ProviderRegistry.get(name)
        assert isinstance(cls.supported_auth, tuple)
        assert len(cls.supported_auth) > 0
        for strat_cls in cls.supported_auth:
            assert issubclass(strat_cls, AuthStrategy)

    def test_unsupported_auth_raises_UnsupportedAuthError(self, name):
        cls = ProviderRegistry.get(name)

        class _NeverSupported(AuthStrategy):
            kind = "_never_supported_in_conformance_tests"
            def detect(self) -> bool:
                return True
            def resolve(self):
                from llm_providers.auth.base import Credential
                return Credential(kind=self.kind, payload={})
            @classmethod
            def default(cls):
                return cls()

        if _NeverSupported in cls.supported_auth:
            pytest.skip("This synthetic strategy is somehow in supported_auth; skip")

        with pytest.raises(UnsupportedAuthError):
            # Construct via __new__ bypass to skip _backend init; we only test
            # _validate_auth here.
            cls._validate_auth(_NeverSupported())

    def test_module_does_not_import_hsb(self, name):
        """Structural assertion: provider modules must not import from hsb.

        Enforced via AST parse, not runtime import, so this fails even when
        hsb is installed."""
        cls = ProviderRegistry.get(name)
        module_path = Path(inspect.getfile(cls))
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("hsb"), (
                    f"{module_path.name} imports from {node.module}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("hsb"), (
                        f"{module_path.name} imports {alias.name}"
                    )


def test_provider_registry_has_at_least_claude_and_openai():
    import llm_providers  # noqa: F401
    names = ProviderRegistry.names()
    assert "claude" in names
    assert "openai" in names
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/llm_providers/test_conformance.py -v`
Expected: all passed.

- [ ] **Step 3: Lint + commit**

```bash
ruff check tests/llm_providers
git add tests/llm_providers/test_conformance.py
git commit -m "test(llm_providers): conformance suite parametrized over providers"
```

---

## Task 15: Library `README.md`

**Files:**
- Create: `src/llm_providers/README.md`

- [ ] **Step 1: Write the README**

`src/llm_providers/README.md`:
```markdown
# llm_providers — Multi-Provider LLM Library

Decoupled, OCP-compliant library for working with multiple LLM execution backends behind one Liskov-substitutable interface. Each provider is one file; adding a new one requires no edits to existing code.

## Mental model — three layers

1. **Protocol** (`protocol.py`, `prompt.py`, `tools.py`, `errors.py`) — vendor-neutral types every provider speaks. `ProviderOptions`, `Capabilities`, `Message`, `SystemPrompt`, `ToolPolicy`, `LLMProvidersError`.
2. **Providers + Auth** (`providers/`, `auth/`, `base.py`, `registry.py`) — `BaseProvider` ABC; per-vendor concrete classes; `AuthStrategy` ABC; per-mechanism concrete strategies; two decorator registries.
3. **Consumers** (anything outside this library) — call `ProviderRegistry.build_auto("claude", accepted_kinds=...)`, get a `BaseProvider`, use `await provider.query(prompt, options)`.

## Adding a new provider

### 3.1 Create the file

Pick a name (e.g. `mistral`) and create `src/llm_providers/providers/mistral.py`:

\`\`\`python
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
\`\`\`

### 3.2 Add the side-effect import

In `src/llm_providers/providers/__init__.py`:

\`\`\`python
from llm_providers.providers import mistral  # noqa: F401
\`\`\`

That's the only edit to existing code.

### 3.3 Add an optional dependency

In the project's `pyproject.toml`:

\`\`\`toml
[project.optional-dependencies]
mistral = ["mistral-sdk>=1.0"]
\`\`\`

## Adding a new auth strategy

### 4.1 Create the file

`src/llm_providers/auth/oauth2_device_code.py`:

\`\`\`python
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
\`\`\`

### 4.2 Wire it into a provider

In whichever providers should accept it:

\`\`\`python
from llm_providers.auth.oauth2_device_code import OAuth2DeviceCode

class MyProvider(BaseProvider):
    supported_auth = (OAuth2DeviceCode, ApiKey)  # preferred-first
\`\`\`

And add one line to `src/llm_providers/auth/__init__.py`:

\`\`\`python
from llm_providers.auth.oauth2_device_code import OAuth2DeviceCode  # noqa: F401
\`\`\`

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
```

- [ ] **Step 2: Commit**

```bash
git add src/llm_providers/README.md
git commit -m "docs(llm_providers): contributor README"
```

---

## Task 16: hsb-side — `policy.py`

**Files:**
- Create: `src/hsb/runtime/policy.py`
- Create: `tests/runtime/test_policy.py`

- [ ] **Step 1: Write the failing test**

`tests/runtime/test_policy.py`:
```python
"""hsb.runtime.policy — G1 OAuth2-only allowlist + per-agent escape hatch."""
import pytest

from hsb.runtime.policy import allowed_auth_kinds


def test_default_excludes_api_key(monkeypatch):
    for v in ("HSB_AUTH_ALLOW_API_KEY_BACKLOG",):
        monkeypatch.delenv(v, raising=False)
    kinds = set(allowed_auth_kinds("backlog"))
    assert "api_key" not in kinds
    assert "oauth2_cli_token" in kinds


def test_per_agent_escape_hatch_includes_api_key(monkeypatch):
    monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", "1")
    kinds = set(allowed_auth_kinds("backlog"))
    assert "api_key" in kinds


def test_per_agent_escape_hatch_is_per_agent(monkeypatch):
    monkeypatch.setenv("HSB_AUTH_ALLOW_API_KEY_BACKLOG", "1")
    monkeypatch.delenv("HSB_AUTH_ALLOW_API_KEY_UAT", raising=False)
    assert "api_key" in set(allowed_auth_kinds("backlog"))
    assert "api_key" not in set(allowed_auth_kinds("uat"))


def test_returns_frozenset():
    kinds = allowed_auth_kinds("backlog")
    assert isinstance(kinds, frozenset)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_policy.py -v`
Expected: `ModuleNotFoundError: No module named 'hsb.runtime.policy'`

- [ ] **Step 3: Implement `policy.py`**

`src/hsb/runtime/policy.py`:
```python
"""hsb runtime policy — G1 OAuth2-only allowlist + per-agent escape hatch.

The llm_providers library is policy-free; hsb imposes "OAuth2 preferred,
API key only when explicitly allowed per-agent" here.
"""
from __future__ import annotations

import os

_DEFAULT_ALLOWED_AUTH_KINDS: frozenset[str] = frozenset({
    "oauth2_cli_token",
    "oauth2_adc",
    "oauth2_service_account",
})


def allowed_auth_kinds(agent_name: str) -> frozenset[str]:
    """Return the auth-kind allowlist for the given agent.

    Default: OAuth2 strategies only (G1 enforcement).
    Per-agent escape: HSB_AUTH_ALLOW_API_KEY_<AGENT>=1 widens the set to
    include "api_key" for that agent only. Documented in GET-STARTED.md.

    There is intentionally no global toggle — flipping one agent is a
    per-operator decision; flipping all is a project-policy change that
    edits this allowlist directly.
    """
    base = set(_DEFAULT_ALLOWED_AUTH_KINDS)
    if os.environ.get(f"HSB_AUTH_ALLOW_API_KEY_{agent_name.upper()}") == "1":
        base.add("api_key")
    return frozenset(base)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_policy.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/hsb/runtime tests/runtime && mypy src/hsb/runtime
git add src/hsb/runtime/policy.py tests/runtime/test_policy.py
git commit -m "feat(hsb.runtime): G1 OAuth2-only allowlist with per-agent escape hatch"
```

---

## Task 17: hsb-side — `handle.py` with G3 backstop

**Files:**
- Create: `src/hsb/runtime/handle.py`
- Create: `tests/runtime/test_handle.py`

- [ ] **Step 1: Write the failing test**

`tests/runtime/test_handle.py`:
```python
"""HsbProviderHandle — G3 backstop wraps every message."""
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hsb.runtime.handle import HsbProviderHandle
from llm_providers.protocol import Message


class _FakeProvider:
    """Minimal BaseProvider stand-in for handle tests."""
    name = "fake"

    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages

    async def query(self, prompt: str, options) -> AsyncIterator[Message]:
        for m in self._messages:
            yield m

    def client(self, options):
        return MagicMock()


async def test_query_passes_through_clean_messages():
    msgs = [Message(text="hello", is_final=False), Message(text="", is_final=True)]
    handle = HsbProviderHandle(provider=_FakeProvider(msgs), agent_name="test")
    received = []
    async for m in handle.query("hi", options=SimpleNamespace()):
        received.append(m)
    assert len(received) == 2


async def test_g3_fires_on_task_tool_assistant_message(monkeypatch):
    """If a message contains an AssistantMessage with a Task tool_use, G3
    raises and the iteration aborts."""
    # Build a fake AssistantMessage with a Task tool_use block.
    from claude_agent_sdk import AssistantMessage
    task_block = SimpleNamespace(name="Task")
    fake_msg = AssistantMessage.__new__(AssistantMessage)
    fake_msg.content = [task_block]

    msg_with_task = Message(text="", is_final=False, raw=fake_msg)
    msgs = [msg_with_task]
    handle = HsbProviderHandle(provider=_FakeProvider(msgs), agent_name="test")

    with pytest.raises(RuntimeError, match="G3 violation"):
        async for _ in handle.query("hi", options=SimpleNamespace()):
            pass


def test_client_returns_provider_client():
    p = _FakeProvider([])
    handle = HsbProviderHandle(provider=p, agent_name="test")
    result = handle.client(options=SimpleNamespace())
    assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_handle.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `handle.py`**

`src/hsb/runtime/handle.py`:
```python
"""HsbProviderHandle — seam where hsb-side policy wraps the library provider.

Today: applies G3 (Task-tool runtime backstop) to every message yielded by
the wrapped provider.query() iterator. Future hsb-only guards (e.g. G6
auditing) plug in here without touching the library.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.protocol import Message, ProviderOptions


@dataclass(frozen=True)
class HsbProviderHandle:
    """Wraps a BaseProvider and applies hsb-side runtime policy."""
    provider: BaseProvider
    agent_name: str

    @property
    def name(self) -> str:
        return self.provider.name

    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        from hsb.agents._sdk_options import assert_no_task_dispatch
        async for msg in self.provider.query(prompt, options):
            # G3 backstop: assert_no_task_dispatch inspects raw SDK messages.
            # If msg.raw is None (e.g. synthetic final), skip.
            if msg.raw is not None:
                assert_no_task_dispatch(msg.raw)
            yield msg

    def client(self, options: ProviderOptions) -> StatefulClient:
        return self.provider.client(options)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_handle.py -v`
Expected: 3 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/hsb/runtime tests/runtime && mypy src/hsb/runtime
git add src/hsb/runtime/handle.py tests/runtime/test_handle.py
git commit -m "feat(hsb.runtime): HsbProviderHandle with G3 backstop"
```

---

## Task 18: hsb-side — `resolver.py` with data-driven dispatch

**Files:**
- Create: `src/hsb/runtime/resolver.py`
- Create: `tests/runtime/test_resolver.py`

- [ ] **Step 1: Write the failing test**

`tests/runtime/test_resolver.py`:
```python
"""hsb.runtime.resolver — HSB_RUNTIME_<AGENT> routing + hard-blocks + alias."""
import pytest

from hsb.runtime.resolver import resolve_runtime
from hsb.runtime.handle import HsbProviderHandle


def test_default_routes_to_claude(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_BACKLOG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    h = resolve_runtime("backlog")
    assert isinstance(h, HsbProviderHandle)
    assert h.provider.name == "claude"


def test_env_var_routes_to_openai_with_codex_oauth(monkeypatch, tmp_path):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "openai")
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    h = resolve_runtime("backlog")
    assert h.provider.name == "openai"


def test_codex_alias_for_openai_emits_warning(monkeypatch, tmp_path):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    (tmp_path / "config.toml").write_text('forced_login_method = "chatgpt"')
    (tmp_path / "auth.json").write_text('{"access_token": "tok"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    with pytest.warns(DeprecationWarning, match="codex.*openai"):
        h = resolve_runtime("backlog")
    assert h.provider.name == "openai"


def test_invalid_value_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "nope")
    with pytest.raises(ValueError, match="not registered"):
        resolve_runtime("backlog")


def test_wio_blocked_from_openai(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_WIO", "openai")
    with pytest.raises(ValueError, match="hard-blocked"):
        resolve_runtime("wio")


def test_wio_blocked_from_gemini(monkeypatch):
    """Phase A doesn't ship Gemini, but the hard-block list includes it.

    The block check fires before the registry lookup, so this raises
    ValueError(hard-blocked) rather than ProviderNotFoundError."""
    monkeypatch.setenv("HSB_RUNTIME_WIO", "gemini")
    with pytest.raises(ValueError, match="hard-blocked"):
        resolve_runtime("wio")


def test_wio_default_to_claude_works(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_WIO", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    h = resolve_runtime("wio")
    assert h.provider.name == "claude"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_resolver.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `resolver.py`**

`src/hsb/runtime/resolver.py`:
```python
"""hsb-side runtime resolver — HSB_RUNTIME_<AGENT> → HsbProviderHandle.

Data-driven dispatch: no if/elif/else chain on provider names. Adding
Gemini support is purely operational (set HSB_RUNTIME_BACKLOG=gemini).
"""
from __future__ import annotations

import os
import warnings

from hsb.runtime.handle import HsbProviderHandle
from hsb.runtime.policy import allowed_auth_kinds
from llm_providers.errors import ProviderNotFoundError
from llm_providers.registry import ProviderRegistry

# Per-agent provider hard-blocks. Adding a new block is a one-line tuple edit;
# no other code needs to change.
_HARD_BLOCKED: dict[str, tuple[str, ...]] = {
    # WIO uses ClaudeSDKClient stateful session; no other provider can host it
    # in Phase A. Even "gemini" is blocked preemptively for clarity once it
    # arrives in Phase B.
    "wio": ("openai", "gemini"),
}


def resolve_runtime(agent_name: str) -> HsbProviderHandle:
    """Read HSB_RUNTIME_<AGENT_NAME>; default 'claude'. Return a handle with
    hsb-side policy applied (G1 allowlist, hard-blocks, G3 backstop)."""
    env_var = f"HSB_RUNTIME_{agent_name.upper()}"
    raw = os.environ.get(env_var, "claude").strip().lower()

    # Deprecation alias: "codex" → "openai" for one release.
    if raw == "codex":
        warnings.warn(
            f"{env_var}=codex is deprecated; use =openai (Codex CLI OAuth is "
            "selected automatically when ~/.codex/auth.json is present).",
            DeprecationWarning,
            stacklevel=2,
        )
        raw = "openai"

    blocked = _HARD_BLOCKED.get(agent_name.lower(), ())
    if raw in blocked:
        raise ValueError(
            f"{env_var}={raw!r} is hard-blocked for agent {agent_name!r}. "
            f"Blocked providers: {blocked}. See AGENT-CONTRACTS.md."
        )

    try:
        provider = ProviderRegistry.build_auto(
            raw,
            accepted_kinds=allowed_auth_kinds(agent_name),
        )
    except ProviderNotFoundError as e:
        raise ValueError(
            f"{env_var}={raw!r}: provider {raw!r} is not registered. "
            f"Registered providers: {ProviderRegistry.names()}."
        ) from e

    return HsbProviderHandle(provider=provider, agent_name=agent_name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_resolver.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/hsb/runtime tests/runtime && mypy src/hsb/runtime
git add src/hsb/runtime/resolver.py tests/runtime/test_resolver.py
git commit -m "feat(hsb.runtime): data-driven resolver with hard-blocks + codex alias"
```

---

## Task 19: hsb-side — compat shims for `ClaudeRuntime` / `CodexRuntime` imports

**Files:**
- Create: `src/hsb/runtime/compat.py`
- Modify: `src/hsb/runtime/claude.py` (replace with re-export)
- Modify: `src/hsb/runtime/codex.py` (replace with re-export)
- Modify: `src/hsb/runtime/codex_guards.py` (re-export from library)

The existing tests `tests/runtime/test_claude_runtime.py` and `tests/runtime/test_codex_runtime.py` import these classes and exercise their methods. The compat shims must satisfy those imports.

- [ ] **Step 1: Review existing tests to understand the surface they exercise**

```bash
grep -n "ClaudeRuntime\|CodexRuntime" tests/runtime/test_claude_runtime.py tests/runtime/test_codex_runtime.py | head -30
```

Identify which methods are called (`query`, `client`, `name`, `_translate`) and reflect them in the shim.

- [ ] **Step 2: Write the compat shim**

`src/hsb/runtime/compat.py`:
```python
"""Deprecation shims for the legacy hsb.runtime.{claude,codex} surface.

ClaudeRuntime and CodexRuntime kept the project compilable during the
runtime extraction. They wrap a library provider and expose the methods
the existing agents and tests used. New code should use
hsb.runtime.resolver.resolve_runtime(agent_name) instead.
"""
from __future__ import annotations

import warnings
from collections.abc import AsyncIterator
from typing import Any

from llm_providers.auth.api_key import ApiKey
from llm_providers.auth.oauth2_cli import OAuth2CliToken
from llm_providers.protocol import AgentOptions  # type: ignore[attr-defined]
from llm_providers.protocol import Message, ProviderOptions
from llm_providers.registry import ProviderRegistry


def _build_provider(name: str) -> Any:
    """Auto-resolve auth based on present env vars / files."""
    return ProviderRegistry.build_auto(
        name, accepted_kinds={"oauth2_cli_token", "api_key"}
    )


class ClaudeRuntime:
    """Deprecation shim — wraps the library's "claude" provider."""
    name = "claude"

    def __init__(self) -> None:
        warnings.warn(
            "hsb.runtime.claude.ClaudeRuntime is deprecated; use "
            "hsb.runtime.resolver.resolve_runtime(<agent>) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._provider = _build_provider("claude")

    async def query(self, prompt: str, options: ProviderOptions) -> AsyncIterator[Message]:
        async for msg in self._provider.query(prompt, options):
            yield msg

    def client(self, options: ProviderOptions):
        return self._provider.client(options)


class CodexRuntime:
    """Deprecation shim — wraps the library's "openai" provider with Codex backend."""
    name = "codex"

    def __init__(self, codex_home=None) -> None:  # codex_home preserved for signature compat
        warnings.warn(
            "hsb.runtime.codex.CodexRuntime is deprecated; use "
            "hsb.runtime.resolver.resolve_runtime(<agent>) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # codex_home is honored via CODEX_HOME env var (handled by the library).
        self._provider = _build_provider("openai")

    async def query(self, prompt: str, options: ProviderOptions) -> AsyncIterator[Message]:
        async for msg in self._provider.query(prompt, options):
            yield msg

    def client(self, options: ProviderOptions):
        return self._provider.client(options)
```

`src/hsb/runtime/claude.py`:
```python
"""Deprecated. See hsb.runtime.compat.ClaudeRuntime."""
from hsb.runtime.compat import ClaudeRuntime  # noqa: F401

__all__ = ["ClaudeRuntime"]
```

`src/hsb/runtime/codex.py`:
```python
"""Deprecated. See hsb.runtime.compat.CodexRuntime."""
from hsb.runtime.compat import CodexRuntime  # noqa: F401

__all__ = ["CodexRuntime"]
```

`src/hsb/runtime/codex_guards.py`:
```python
"""Re-exports of the library's Codex config parser for backward compat.

The implementation lives in llm_providers.providers._codex_config; this
module exists so existing imports (`from hsb.runtime.codex_guards import ...`)
keep working.
"""
from llm_providers.providers._codex_config import (
    _resolve_codex_home,
    assert_codex_oauth_only,
    verify_codex_mcp,
)

__all__ = ["_resolve_codex_home", "assert_codex_oauth_only", "verify_codex_mcp"]
```

- [ ] **Step 3: Run existing tests to verify they still pass**

```bash
pytest tests/runtime/test_claude_runtime.py tests/runtime/test_codex_runtime.py \
       tests/runtime/test_codex_guards.py -v -W ignore::DeprecationWarning
```

Expected: all pass. If failures show specific method signatures the shim doesn't cover, extend `compat.py` accordingly (the underlying `BaseProvider` exposes `query` and `client`; if a test calls `_to_message`, `_translate`, or another protected method, add a delegating method on the shim).

- [ ] **Step 4: Commit**

```bash
ruff check src/hsb/runtime && mypy src/hsb/runtime
git add src/hsb/runtime/compat.py src/hsb/runtime/claude.py \
        src/hsb/runtime/codex.py src/hsb/runtime/codex_guards.py
git commit -m "refactor(hsb.runtime): replace ClaudeRuntime/CodexRuntime with compat shims"
```

---

## Task 20: hsb-side — update `protocol.py` to alias library types

**Files:**
- Modify: `src/hsb/runtime/protocol.py`
- Modify: `src/hsb/runtime/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/runtime/test_protocol.py` (append, don't replace):
```python
"""Existing tests continue; add aliasing assertions."""

def test_agent_options_is_provider_options():
    from hsb.runtime.protocol import AgentOptions
    from llm_providers.protocol import ProviderOptions
    assert AgentOptions is ProviderOptions


def test_message_re_exported():
    from hsb.runtime.protocol import Message as HsbMessage
    from llm_providers.protocol import Message as LibMessage
    assert HsbMessage is LibMessage


def test_runtime_protocol_aliases_baseprovider():
    """The legacy Runtime Protocol becomes an alias for BaseProvider.

    isinstance(x, Runtime) checks should keep working for one release."""
    from hsb.runtime.protocol import Runtime
    from llm_providers.base import BaseProvider
    # Runtime is now a TypeAlias for BaseProvider — assert the binding.
    assert Runtime is BaseProvider or issubclass(BaseProvider, Runtime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_protocol.py -v`
Expected: `AssertionError` on `AgentOptions is ProviderOptions`.

- [ ] **Step 3: Update `protocol.py`**

Replace `src/hsb/runtime/protocol.py`:
```python
"""hsb.runtime.protocol — aliases over llm_providers.protocol.

AgentOptions is the canonical option type for hsb agents; it's now a
straight alias for ProviderOptions. Message is re-exported. The legacy
`Runtime` Protocol becomes an alias for BaseProvider so isinstance checks
in existing code keep working through the deprecation window.
"""
from __future__ import annotations

from typing import TypeAlias

from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)

# Canonical alias for hsb code paths.
AgentOptions: TypeAlias = ProviderOptions

# Legacy alias kept for the deprecation window. `isinstance(x, Runtime)`
# remains valid for any BaseProvider subclass.
Runtime: TypeAlias = BaseProvider

# Preserve the legacy literal type for any caller that imported it.
RuntimeName: TypeAlias = str

__all__ = [
    "AgentOptions",
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
    "Runtime",
    "RuntimeName",
    "StatefulClient",
]
```

Update `src/hsb/runtime/__init__.py`:
```python
"""hsb.runtime — thin consumer adapter over llm_providers."""
from hsb.runtime.protocol import (
    AgentOptions,
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
    Runtime,
    RuntimeName,
    StatefulClient,
)

__all__ = [
    "AgentOptions",
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
    "Runtime",
    "RuntimeName",
    "StatefulClient",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_protocol.py -v`
Expected: existing tests still pass + 3 new pass.

- [ ] **Step 5: Lint + commit**

```bash
ruff check src/hsb/runtime tests/runtime && mypy src/hsb/runtime
git add src/hsb/runtime/protocol.py src/hsb/runtime/__init__.py tests/runtime/test_protocol.py
git commit -m "refactor(hsb.runtime): alias AgentOptions/Message to llm_providers types"
```

---

## Task 21: Rewire `_sdk_options.py` to consume the library

**Files:**
- Modify: `src/hsb/agents/_sdk_options.py`

**Goal:** `assert_oauth2_only()` delegates to `policy.allowed_auth_kinds()`. `resolve_runtime()` becomes a one-line wrapper. `make_options()` keeps its signature unchanged. `make_agent_options()` continues to return a library-compatible `AgentOptions` (already does — now it's literally `ProviderOptions`).

- [ ] **Step 1: Run the existing test suite to capture baseline**

```bash
pytest tests/runtime/test_oauth_guard.py tests/runtime/test_make_options_branches.py \
       tests/runtime/test_resolve_runtime.py tests/runtime/test_make_agent_options.py -v
```

Note any tests that fail (these become the regression set we must preserve).

- [ ] **Step 2: Refactor `assert_oauth2_only()` to delegate**

Open `src/hsb/agents/_sdk_options.py` and modify the function:

```python
def assert_oauth2_only(agent_name: str | None = None) -> None:
    """G1 (AI-SPEC §6) — function-entry-time guard.

    Now delegates to hsb.runtime.policy.allowed_auth_kinds. When agent_name
    is provided, the per-agent escape hatch (HSB_AUTH_ALLOW_API_KEY_<AGENT>)
    is honored. When None (legacy callers in make_options), the strict
    default (no api_key allowed) is enforced — matching the historical
    behavior of rejecting ANTHROPIC_API_KEY / OPENAI_API_KEY.
    """
    from hsb.runtime.policy import allowed_auth_kinds
    kinds = allowed_auth_kinds(agent_name or "__default__")
    if "api_key" in kinds:
        return  # api_key explicitly allowed for this agent — bypass the guard
    forbidden = [v for v in _FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex), or set "
            f"HSB_AUTH_ALLOW_API_KEY_<AGENT>=1 to allow this agent."
        )
```

- [ ] **Step 3: Refactor `resolve_runtime()` to wrap library**

Replace the existing function body with:

```python
def resolve_runtime(agent_name: str):
    """Return the runtime handle for the given agent.

    Delegates to hsb.runtime.resolver.resolve_runtime, which routes through
    the llm_providers library. Existing callers see a HsbProviderHandle
    that exposes .name, .query(), and .client() — superset of the old
    ClaudeRuntime/CodexRuntime API.
    """
    from hsb.runtime.resolver import resolve_runtime as _resolve
    return _resolve(agent_name)
```

- [ ] **Step 4: `make_agent_options()` — switch to building a ProviderOptions**

Replace the existing body with:

```python
def make_agent_options(
    system_prompt: str,
    allowed_tools,
    permission_mode,
    max_turns: int,
    model: str,
    mcp_servers: dict | None = None,
    cwd: str | None = None,
    output_schema: dict | None = None,
    hooks=None,
):
    """Runtime-agnostic options factory. Returns ProviderOptions (aliased
    as AgentOptions for legacy imports).

    Enforces G1 + G2 (same as make_options). Use this when an agent goes
    through the runtime adapter; use make_options() when an agent still
    calls claude_agent_sdk directly.
    """
    from llm_providers.prompt import TextSystemPrompt
    from llm_providers.protocol import ProviderOptions
    from llm_providers.tools import McpServerSpec, ToolPolicy

    assert_oauth2_only()  # G1
    forbidden = _FORBIDDEN_TOOLS & set(allowed_tools)
    if forbidden:
        raise ValueError(
            f"G2 violation: {forbidden} must not appear in allowed_tools. "
            "Sub-subagent dispatch is forbidden by WORC-02."
        )

    # Translate legacy mcp_servers dict to McpServerSpec tuple.
    mcp_specs: tuple[McpServerSpec, ...] = ()
    if mcp_servers:
        mcp_specs = tuple(
            McpServerSpec(
                name=name,
                transport=cfg.get("transport", "stdio"),
                command=tuple(cfg["command"]) if "command" in cfg else None,
                url=cfg.get("url"),
                env=cfg.get("env", {}),
            )
            for name, cfg in mcp_servers.items()
        )

    extras = {}
    if hooks is not None:
        extras["claude"] = {"hooks": hooks}

    return ProviderOptions(
        system_prompt=TextSystemPrompt(text=system_prompt),
        model=model,
        max_turns=max_turns,
        tool_policy=ToolPolicy(allowed=tuple(allowed_tools)),
        mcp_servers=mcp_specs,
        permission_mode=permission_mode,
        output_schema=output_schema,
        cwd=cwd,
        extras=extras,
    )
```

- [ ] **Step 5: `make_options()` — leave unchanged**

`make_options()` still returns `ClaudeAgentOptions` directly (used by direct-SDK agents like UAT). Its signature and behavior do not change. The only edit: ensure the `assert_oauth2_only()` call inside it now passes no `agent_name` (so the strict default applies).

Verify by reading the function — if it calls `assert_oauth2_only()` with no argument, no change needed.

- [ ] **Step 6: Run the full test suite**

```bash
pytest tests/ -v -W ignore::DeprecationWarning
```

Expected: all tests pass. If anything fails, fix the shim/handle/option translation rather than the test (the existing tests encode the contract).

- [ ] **Step 7: Lint + commit**

```bash
ruff check src/hsb && mypy src/hsb
git add src/hsb/agents/_sdk_options.py
git commit -m "refactor(hsb): route _sdk_options through llm_providers library"
```

---

## Task 22: Update `pyproject.toml` for the library package

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit the wheel-build target**

In `pyproject.toml`, update:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/hsb", "src/llm_providers"]
```

- [ ] **Step 2: Verify the install still works**

```bash
pip install -e ".[dev]"
python -c "import llm_providers; print(llm_providers.ProviderRegistry.names())"
```

Expected output: `('claude', 'openai')`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: include src/llm_providers in wheel package list"
```

---

## Task 23: Full-suite green check + final commit

- [ ] **Step 1: Run the entire test suite**

```bash
pytest tests/ -v -W ignore::DeprecationWarning
```

Expected: all green (existing + new). If any failure remains, fix it before moving on. **Do not commit fixes for unrelated test failures — investigate first.**

- [ ] **Step 2: Run lint + types across both packages**

```bash
ruff check src/ tests/
mypy src/llm_providers src/hsb
```

Expected: clean.

- [ ] **Step 3: Spot-check the backlog agent end-to-end**

The Backlog Agent is the only agent already on the runtime adapter. Verify its parity test still passes:

```bash
pytest tests/integration/test_backlog_runtime_parity.py -v -W ignore::DeprecationWarning
```

Expected: pass.

- [ ] **Step 4: Sanity-check `hsb --help` still loads**

```bash
hsb --help
```

Expected: Typer CLI prints help without error.

- [ ] **Step 5: If any fixes were made in this task, commit them**

```bash
git status
# If clean, no commit needed.
# Otherwise:
git add -p  # review each fix
git commit -m "fix: address regressions found in Phase A full-suite check"
```

---

## Self-review (already applied)

After drafting this plan, I checked it against the spec:

- **Spec §4 file layout** — every file listed in the design appears in the "File Structure" section and is owned by exactly one task.
- **Spec §5 abstractions** — `ProviderOptions`, `Capabilities`, `BaseProvider`, `SystemPrompt`, `ToolPolicy` each get a dedicated task (Tasks 1, 3, 4, 8).
- **Spec §6 auth** — `AuthStrategy`, `Credential`, `ApiKey`, `OAuth2CliToken` (Tasks 5, 6, 7). `OAuth2Adc` / `OAuth2ServiceAccount` are explicitly Phase B (deferred to Gemini plan).
- **Spec §7 providers** — `ClaudeProvider` (Task 11), `OpenAIProvider` with dual backends (Task 12). Codex config porting (Task 10).
- **Spec §8 registry** — `ProviderRegistry` + `AuthRegistry` + `auto_resolve_auth` (Task 9). Side-effect imports (Task 13).
- **Spec §9 README** — Task 15.
- **Spec §10 hsb.runtime adapter** — `policy.py` (Task 16), `handle.py` (Task 17), `resolver.py` (Task 18), `compat.py` + legacy shims (Task 19), `protocol.py` aliasing (Task 20), `_sdk_options.py` rewire (Task 21).
- **Spec §11 consumer impact** — Task 21 + Task 23's spot-checks of Backlog parity + `hsb --help` verify "no agent code changes."
- **Spec §12 errors** — Task 2.
- **Spec §13 testing** — conformance suite (Task 14), per-provider/per-strategy tests in their owning tasks, consumer-side policy/resolver/handle tests in Tasks 16/17/18.
- **Spec §14 packaging** — Task 22.

No placeholders detected. Method names, attribute names, and class names are consistent across tasks (`ProviderRegistry.register`, `BaseProvider._validate_auth`, `Capabilities.supports_mcp`, etc.).

Phase A is fully covered. Phases B and C will be planned separately when their time comes.
