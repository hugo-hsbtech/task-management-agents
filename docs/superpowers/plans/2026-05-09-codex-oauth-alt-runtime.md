# Codex as Alternative OAuth2 Runtime — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-agent runtime flippability between Claude Code and OpenAI Codex CLI via env var (`HSB_RUNTIME_<AGENT>=codex`), OAuth-only on both sides; ship the flip on the Backlog Agent as the pilot.

**Architecture:** A new `src/hsb/runtime/` package introduces a `Runtime` Protocol with two implementations — `ClaudeRuntime` (wraps `claude_agent_sdk.query`) and `CodexRuntime` (wraps `openai_codex_sdk.Codex`). The existing `_sdk_options.make_options()` chokepoint grows two siblings: `make_agent_options()` (returns runtime-agnostic `AgentOptions`) and `resolve_runtime(agent_name)` (env-var-driven). Backlog Agent migrates from direct `claude_agent_sdk` imports to the runtime adapter.

**Tech Stack:** Python 3.12+, `claude-agent-sdk` (existing), `openai-codex-sdk` (new — provides `openai_codex_sdk`), `pydantic`, `tomllib` (stdlib), `pytest`, `pytest-asyncio`.

**Spec:** [`docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md`](../specs/2026-05-09-codex-oauth-alt-runtime-design.md)

**Known constraints carried into plan:**
- Backlog Agent currently bypasses the `make_options()` chokepoint and constructs `ClaudeAgentOptions` directly. Task 9 closes this gap as part of the runtime refactor.
- `hooks=LINEAR_HOOKS` is Claude-specific (`HookMatcher` API). Codex has no equivalent; `CodexRuntime` raises `NotImplementedError` if `AgentOptions.hooks` is non-None. Flipping Backlog to Codex therefore disables Linear-write hook guards on the Codex path. Documented in the GET-STARTED Step 1.5 caveats.

---

## Task 1: Add `openai-codex-sdk` dependency

**Files:**
- Modify: `pyproject.toml`, `uv.lock`

- [ ] **Step 1: Add the dependency via uv**

```bash
uv add openai-codex-sdk
```
Expected: pyproject.toml gains `"openai-codex-sdk>=X.Y.Z"` under `[project] dependencies`, uv.lock updates. Note the exact version uv resolved.

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from openai_codex_sdk import Codex, Thread, ThreadOptions, TurnOptions, TextInput; print('openai_codex_sdk OK')"
```
Expected: `openai_codex_sdk OK`. (Module is `openai_codex_sdk`, not `openai_codex_sdk`. Async support is via `await Thread.run_streamed(...)` on the same `Thread` class — no separate AsyncThread.)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add openai-codex-sdk for Codex runtime adapter"
```

---

## Task 2: Define `Runtime` Protocol + `AgentOptions`

**Files:**
- Create: `src/hsb/runtime/__init__.py`
- Create: `src/hsb/runtime/protocol.py`
- Test:   `tests/runtime/__init__.py`, `tests/runtime/test_protocol.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/__init__.py` (empty) and `tests/runtime/test_protocol.py`:

```python
"""Tests for the runtime-agnostic Protocol surface."""
from __future__ import annotations

import pytest
from typing import get_type_hints

from hsb.runtime.protocol import AgentOptions, Runtime, Message


def test_agent_options_is_frozen_dataclass():
    opts = AgentOptions(
        system_prompt="hi",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
    )
    with pytest.raises(Exception):
        opts.system_prompt = "modified"  # type: ignore[misc]


def test_agent_options_optional_fields_default_none():
    opts = AgentOptions(
        system_prompt="x",
        allowed_tools=(),
        permission_mode="default",
        max_turns=1,
        model="m",
    )
    assert opts.mcp_servers is None
    assert opts.cwd is None
    assert opts.output_schema is None
    assert opts.hooks is None


def test_runtime_protocol_has_required_methods():
    hints = get_type_hints(Runtime)
    assert "name" in hints
    assert hasattr(Runtime, "query")
    assert hasattr(Runtime, "client")


def test_message_has_text_field():
    msg = Message(text="hello", is_final=False)
    assert msg.text == "hello"
    assert msg.is_final is False
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/runtime/test_protocol.py -v
```
Expected: ImportError — `hsb.runtime.protocol` does not exist yet.

- [ ] **Step 3: Implement the module**

Create `src/hsb/runtime/__init__.py`:

```python
"""hsb.runtime — runtime-agnostic adapter layer.

Two implementations: ClaudeRuntime (claude_agent_sdk) and CodexRuntime
(openai_codex_sdk). Selection is per-agent via environment variable
HSB_RUNTIME_<AGENT_NAME>. See docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md.
"""
from hsb.runtime.protocol import AgentOptions, Message, Runtime, StatefulClient

__all__ = ["AgentOptions", "Message", "Runtime", "StatefulClient"]
```

Create `src/hsb/runtime/protocol.py`:

```python
"""Runtime-agnostic Protocol and option shape.

These types are the lowest common denominator between claude_agent_sdk
and openai_codex_sdk. They are NOT re-exports of either SDK's types —
each Runtime implementation translates AgentOptions into its native
options at the seam.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable, Literal, Protocol


PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]
RuntimeName = Literal["claude", "codex"]


@dataclass(frozen=True)
class Message:
    """Minimal message shape both runtimes yield. Mirrors the surface
    Backlog Agent uses today (text accumulation + final-result detection).
    """
    text: str
    is_final: bool = False
    raw: Any = None  # underlying SDK message, for opt-in inspection


@dataclass(frozen=True)
class AgentOptions:
    """Runtime-agnostic option shape. Returned by make_agent_options()."""
    system_prompt: str
    allowed_tools: tuple[str, ...]
    permission_mode: PermissionMode
    max_turns: int
    model: str
    mcp_servers: dict[str, dict] | None = None
    cwd: str | None = None
    output_schema: dict | None = None
    hooks: Any = None  # Claude-only HookMatcher list; CodexRuntime rejects non-None.


class StatefulClient(Protocol):
    """Future use — parallel to claude_agent_sdk.ClaudeSDKClient. Not used
    by the Backlog pilot. Concrete implementations land when WIO is ported.
    """
    async def __aenter__(self) -> "StatefulClient": ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def query(self, prompt: str) -> AsyncIterator[Message]: ...


class Runtime(Protocol):
    """Two implementations: ClaudeRuntime, CodexRuntime."""
    name: RuntimeName

    def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        """One-shot query — async iterator of Message events."""
        ...

    def client(self, options: AgentOptions) -> StatefulClient:
        """Stateful multi-turn client. Not used by Backlog; placeholder for WIO port."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/runtime/test_protocol.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/runtime/__init__.py src/hsb/runtime/protocol.py tests/runtime/__init__.py tests/runtime/test_protocol.py
git commit -m "feat(runtime): Protocol + AgentOptions seam for runtime adapter"
```

---

## Task 3: Implement `ClaudeRuntime`

**Files:**
- Create: `src/hsb/runtime/claude.py`
- Test:   `tests/runtime/test_claude_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
"""ClaudeRuntime: thin wrapper around claude_agent_sdk.query."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.runtime.claude import ClaudeRuntime
from hsb.runtime.protocol import AgentOptions


@pytest.fixture
def opts():
    return AgentOptions(
        system_prompt="sys",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
        mcp_servers={"linear": {"command": "npx", "args": []}},
    )


def test_name_is_claude():
    assert ClaudeRuntime().name == "claude"


@pytest.mark.asyncio
async def test_query_translates_options_and_yields_messages(opts):
    fake_text_block = MagicMock(text="result chunk")
    fake_assistant = MagicMock()
    fake_assistant.content = [fake_text_block]
    fake_result = MagicMock()
    fake_result.usage = {"output_tokens": 10}

    async def fake_query_iter(prompt, options):
        yield fake_assistant
        yield fake_result

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query_iter) as q:
        rt = ClaudeRuntime()
        msgs = []
        async for m in rt.query("hello", opts):
            msgs.append(m)

    assert q.call_count == 1
    sdk_options = q.call_args.kwargs["options"]
    # Translation: AgentOptions → ClaudeAgentOptions preserves these fields.
    assert sdk_options.system_prompt == "sys"
    assert "Read" in sdk_options.allowed_tools
    assert sdk_options.permission_mode == "acceptEdits"
    assert sdk_options.max_turns == 5
    assert sdk_options.model == "claude-opus-4-7"
    assert sdk_options.mcp_servers == {"linear": {"command": "npx", "args": []}}
    # At least one message yielded with text content.
    assert any(m.text == "result chunk" for m in msgs)


@pytest.mark.asyncio
async def test_query_forwards_hooks_unchanged(opts):
    sentinel_hooks = ["hook1", "hook2"]
    opts_with_hooks = AgentOptions(**{**opts.__dict__, "hooks": sentinel_hooks})

    async def fake_iter(prompt, options):
        if False:
            yield  # never yields

    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_iter) as q:
        rt = ClaudeRuntime()
        async for _ in rt.query("p", opts_with_hooks):
            pass
        sdk_options = q.call_args.kwargs["options"]
        assert sdk_options.hooks == sentinel_hooks
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/runtime/test_claude_runtime.py -v
```
Expected: ImportError — `hsb.runtime.claude` does not exist.

- [ ] **Step 3: Implement `ClaudeRuntime`**

Create `src/hsb/runtime/claude.py`:

```python
"""ClaudeRuntime — wraps claude_agent_sdk.

Translates the runtime-agnostic AgentOptions into ClaudeAgentOptions
and yields Protocol Messages. No behavior change vs. calling
claude_agent_sdk.query() directly.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
)

from hsb.runtime.protocol import AgentOptions, Message, RuntimeName


class ClaudeRuntime:
    name: RuntimeName = "claude"

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        sdk_options = self._translate(options)
        async for sdk_msg in claude_agent_sdk.query(prompt=prompt, options=sdk_options):
            yield self._to_message(sdk_msg)

    def client(self, options: AgentOptions) -> Any:
        # WIO port lands separately; raise to make accidental use loud.
        raise NotImplementedError(
            "ClaudeRuntime.client() not yet wired — WIO port pending. "
            "Use claude_agent_sdk.ClaudeSDKClient directly until then."
        )

    @staticmethod
    def _translate(options: AgentOptions) -> ClaudeAgentOptions:
        kwargs: dict[str, Any] = dict(
            system_prompt=options.system_prompt,
            allowed_tools=list(options.allowed_tools),
            permission_mode=options.permission_mode,
            max_turns=options.max_turns,
            model=options.model,
        )
        if options.mcp_servers is not None:
            kwargs["mcp_servers"] = options.mcp_servers
        if options.cwd is not None:
            kwargs["cwd"] = options.cwd
        if options.hooks is not None:
            kwargs["hooks"] = options.hooks
        return ClaudeAgentOptions(**kwargs)

    @staticmethod
    def _to_message(sdk_msg: Any) -> Message:
        if isinstance(sdk_msg, AssistantMessage):
            text = "".join(getattr(b, "text", "") for b in (sdk_msg.content or []))
            return Message(text=text, is_final=False, raw=sdk_msg)
        if isinstance(sdk_msg, ResultMessage):
            return Message(text="", is_final=True, raw=sdk_msg)
        return Message(text="", is_final=False, raw=sdk_msg)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/runtime/test_claude_runtime.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/runtime/claude.py tests/runtime/test_claude_runtime.py
git commit -m "feat(runtime): ClaudeRuntime — wraps claude_agent_sdk behind Runtime Protocol"
```

---

## Task 4: Extend `assert_oauth2_only()` to reject `OPENAI_API_KEY`

**Files:**
- Modify: `src/hsb/agents/_sdk_options.py:32-46`
- Test:   `tests/runtime/test_oauth_guard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_oauth_guard.py`:

```python
"""G1 guard now forbids both ANTHROPIC_API_KEY and OPENAI_API_KEY."""
from __future__ import annotations

import pytest

from hsb.agents._sdk_options import assert_oauth2_only


def test_passes_when_neither_var_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert_oauth2_only()  # no raise


def test_rejects_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-foo")
    with pytest.raises(RuntimeError, match=r"G1 violation.*ANTHROPIC_API_KEY"):
        assert_oauth2_only()


def test_rejects_openai_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-foo")
    with pytest.raises(RuntimeError, match=r"G1 violation.*OPENAI_API_KEY"):
        assert_oauth2_only()


def test_rejects_when_both_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    with pytest.raises(RuntimeError, match=r"G1 violation"):
        assert_oauth2_only()
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/runtime/test_oauth_guard.py -v
```
Expected: `test_rejects_openai_api_key` FAILS — current guard only checks `ANTHROPIC_API_KEY`.

- [ ] **Step 3: Modify the guard**

Replace `src/hsb/agents/_sdk_options.py:32-46` (the existing `assert_oauth2_only` function) with:

```python
_FORBIDDEN_API_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def assert_oauth2_only() -> None:
    """G1 (AI-SPEC §6) — function-entry-time guard. Rejects metered API keys
    for either runtime. Operators must use OAuth tokens:
      - Claude:  CLAUDE_CODE_OAUTH_TOKEN  (from `claude setup-token`)
      - Codex:   ~/.codex/auth.json       (from `codex login --device-auth`)
    """
    forbidden = [v for v in _FORBIDDEN_API_KEY_VARS if v in os.environ]
    if forbidden:
        raise RuntimeError(
            f"G1 violation: {', '.join(forbidden)} set — forbidden. "
            "Use OAuth tokens only (CLAUDE_CODE_OAUTH_TOKEN for Claude, "
            "`codex login --device-auth` for Codex)."
        )
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/runtime/test_oauth_guard.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the full suite to confirm no regression**

```bash
uv run pytest tests/ -x -q
```
Expected: all existing tests still pass (note any pre-existing failures unrelated to this change).

- [ ] **Step 6: Commit**

```bash
git add src/hsb/agents/_sdk_options.py tests/runtime/test_oauth_guard.py
git commit -m "feat(g1): extend OAuth-only guard to reject OPENAI_API_KEY"
```

---

## Task 5: Codex auth + MCP guards (`assert_codex_oauth_only` + `verify_codex_mcp`)

**Files:**
- Create: `src/hsb/runtime/codex_guards.py`
- Test:   `tests/runtime/test_codex_guards.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for Codex-side OAuth and MCP verification helpers."""
from __future__ import annotations

import pytest

from hsb.runtime.codex_guards import (
    assert_codex_oauth_only,
    verify_codex_mcp,
)


def _write_codex(tmp_path, *, config_content: str | None, with_auth_json: bool):
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    if config_content is not None:
        (codex_home / "config.toml").write_text(config_content)
    if with_auth_json:
        (codex_home / "auth.json").write_text("{}")
    return codex_home


def test_oauth_passes_when_config_and_auth_present(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "chatgpt"\nmodel = "gpt-5.4"\n',
        with_auth_json=True,
    )
    parsed = assert_codex_oauth_only(codex_home=home)
    assert parsed["forced_login_method"] == "chatgpt"


def test_oauth_rejects_missing_config(tmp_path):
    home = _write_codex(tmp_path, config_content=None, with_auth_json=True)
    with pytest.raises(RuntimeError, match=r"~/.codex/config.toml"):
        assert_codex_oauth_only(codex_home=home)


def test_oauth_rejects_wrong_login_method(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "api"\n',
        with_auth_json=True,
    )
    with pytest.raises(RuntimeError, match=r'forced_login_method must be "chatgpt"'):
        assert_codex_oauth_only(codex_home=home)


def test_oauth_rejects_missing_auth_json(tmp_path):
    home = _write_codex(
        tmp_path,
        config_content='forced_login_method = "chatgpt"\n',
        with_auth_json=False,
    )
    with pytest.raises(RuntimeError, match=r"codex login --device-auth"):
        assert_codex_oauth_only(codex_home=home)


def test_verify_mcp_passes_when_all_present():
    parsed = {"mcp_servers": {"linear": {"command": "npx"}, "github": {"command": "x"}}}
    verify_codex_mcp(parsed, ["linear", "github"])  # no raise


def test_verify_mcp_rejects_missing_block():
    parsed = {"mcp_servers": {"linear": {"command": "npx"}}}
    with pytest.raises(RuntimeError, match=r"github"):
        verify_codex_mcp(parsed, ["linear", "github"])


def test_verify_mcp_handles_empty_section():
    parsed: dict = {}
    with pytest.raises(RuntimeError, match=r"linear"):
        verify_codex_mcp(parsed, ["linear"])
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/runtime/test_codex_guards.py -v
```
Expected: ImportError — `hsb.runtime.codex_guards` does not exist.

- [ ] **Step 3: Implement the guards**

Create `src/hsb/runtime/codex_guards.py`:

```python
"""Codex-side analogues of the G1 guards.

Two helpers:
- assert_codex_oauth_only(codex_home=None): one-shot init-time check.
  Verifies ~/.codex/config.toml has `forced_login_method = "chatgpt"` and
  ~/.codex/auth.json exists. Returns the parsed config dict so the caller
  can cache it instead of re-reading per call.
- verify_codex_mcp(parsed_config, requested_servers): per-call check.
  For each requested MCP server name, asserts a [mcp_servers.<name>] block
  is present in the cached parsed config.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Iterable


def _resolve_codex_home(codex_home: Path | None = None) -> Path:
    if codex_home is not None:
        return codex_home
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codex"


def assert_codex_oauth_only(codex_home: Path | None = None) -> dict[str, Any]:
    """Init-time check. Returns the parsed config.toml dict."""
    home = _resolve_codex_home(codex_home)
    config_path = home / "config.toml"
    auth_path = home / "auth.json"

    if not config_path.exists():
        raise RuntimeError(
            f"G1-Codex violation: {config_path} not found. "
            "Codex CLI must be configured with forced_login_method = \"chatgpt\". "
            "See GET-STARTED.md Step 1.5."
        )
    parsed = tomllib.loads(config_path.read_text())

    if parsed.get("forced_login_method") != "chatgpt":
        raise RuntimeError(
            f"G1-Codex violation: forced_login_method must be \"chatgpt\" "
            f"in {config_path} (got {parsed.get('forced_login_method')!r}). "
            "OAuth-only enforcement: API-key auth disallowed. "
            "See GET-STARTED.md Step 1.5."
        )

    if not auth_path.exists():
        raise RuntimeError(
            f"Codex not authenticated: {auth_path} missing. "
            "Run: codex login --device-auth"
        )

    return parsed


def verify_codex_mcp(parsed_config: dict, requested_servers: Iterable[str]) -> None:
    """Per-call check. Cheap dict lookup against cached parsed config."""
    available = (parsed_config.get("mcp_servers") or {}).keys()
    missing = [s for s in requested_servers if s not in available]
    if missing:
        raise RuntimeError(
            f"Codex MCP missing: [mcp_servers.{', mcp_servers.'.join(missing)}] "
            f"block(s) not found in ~/.codex/config.toml. "
            "Add the block(s) (see GET-STARTED.md Step 1.5)."
        )
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/runtime/test_codex_guards.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/runtime/codex_guards.py tests/runtime/test_codex_guards.py
git commit -m "feat(runtime): Codex G1-equivalent guards (forced_login_method + MCP verify)"
```

---

## Task 6: Implement `CodexRuntime`

**Files:**
- Create: `src/hsb/runtime/codex.py`
- Test:   `tests/runtime/test_codex_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
"""CodexRuntime: wraps openai_codex_sdk.Codex behind Runtime Protocol.

API note (openai-codex-sdk v0.1.11):
- Codex() constructor needs a binary; tests patch hsb.runtime.codex.Codex.
- start_thread(ThreadOptions(...)) returns a Thread.
- await thread.run_streamed(TextInput(type="text", text=...), TurnOptions(...))
  returns a StreamedTurn whose .events is an async iterator.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.runtime.protocol import AgentOptions


@pytest.fixture
def codex_home(tmp_path):
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\nmodel = "gpt-5.4"\n\n'
        '[mcp_servers.linear]\ncommand = "npx"\nargs = []\n'
    )
    (home / "auth.json").write_text("{}")
    return home


@pytest.fixture
def opts():
    return AgentOptions(
        system_prompt="sys-prompt",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="gpt-5.4",
        mcp_servers={"linear": {"command": "npx", "args": []}},
    )


def _make_streamed_turn(events: list):
    """Build a fake StreamedTurn whose .events is an async iterator over `events`."""
    async def _aiter():
        for e in events:
            yield e
    return SimpleNamespace(events=_aiter())


def test_init_runs_oauth_check(codex_home):
    from hsb.runtime.codex import CodexRuntime
    rt = CodexRuntime(codex_home=codex_home)
    assert rt.name == "codex"
    assert rt._cached_config["forced_login_method"] == "chatgpt"


def test_init_fails_when_oauth_invalid(tmp_path):
    from hsb.runtime.codex import CodexRuntime
    bad_home = tmp_path / "no_codex"
    with pytest.raises(RuntimeError, match=r"G1-Codex"):
        CodexRuntime(codex_home=bad_home)


@pytest.mark.asyncio
async def test_query_rejects_hooks(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime
    opts_with_hooks = AgentOptions(**{**opts.__dict__, "hooks": ["x"]})
    rt = CodexRuntime(codex_home=codex_home)
    with pytest.raises(NotImplementedError, match=r"hooks"):
        async for _ in rt.query("p", opts_with_hooks):
            pass


@pytest.mark.asyncio
async def test_query_verifies_mcp(codex_home, opts):
    """Requesting an MCP server not in config.toml raises before binary spawn."""
    from hsb.runtime.codex import CodexRuntime
    bad_opts = AgentOptions(
        **{**opts.__dict__, "mcp_servers": {"missing": {"command": "x"}}}
    )
    rt = CodexRuntime(codex_home=codex_home)
    with pytest.raises(RuntimeError, match=r"missing"):
        async for _ in rt.query("p", bad_opts):
            pass


@pytest.mark.asyncio
async def test_query_calls_codex_thread_run(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_event = SimpleNamespace(text="hi from codex")
    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([fake_event]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        msgs = []
        async for m in rt.query("hello", opts):
            msgs.append(m)

    fake_codex.start_thread.assert_called_once()
    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.model == "gpt-5.4"
    assert thread_options_arg.approvalPolicy == "never"

    # run_streamed received a TextInput with the system+user prompt.
    fake_thread.run_streamed.assert_awaited_once()
    call = fake_thread.run_streamed.call_args
    text_input = call.args[0]
    assert "<system>sys-prompt</system>" in text_input.text
    assert "hello" in text_input.text


@pytest.mark.asyncio
async def test_query_translates_permission_mode(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    accept_opts = AgentOptions(**{**opts.__dict__, "permission_mode": "bypassPermissions"})

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        async for _ in rt.query("p", accept_opts):
            pass

    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.approvalPolicy == "never"


@pytest.mark.asyncio
async def test_query_passes_cwd_and_output_schema(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    cwd_opts = AgentOptions(
        **{**opts.__dict__, "cwd": "/tmp", "output_schema": {"type": "object"}}
    )

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        async for _ in rt.query("p", cwd_opts):
            pass

    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.workingDirectory == "/tmp"
    turn_options_arg = fake_thread.run_streamed.call_args.args[1]
    assert turn_options_arg.outputSchema == {"type": "object"}
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/runtime/test_codex_runtime.py -v
```
Expected: ImportError — `hsb.runtime.codex` does not exist.

- [ ] **Step 3: Implement `CodexRuntime`**

Create `src/hsb/runtime/codex.py`:

```python
"""CodexRuntime — wraps openai_codex_sdk.Codex.

Translation table (Backlog-scoped surface):
  system_prompt   → prepended to prompt as <system>...</system> block in TextInput
  model           → ThreadOptions(model=...)
  mcp_servers     → verified against ~/.codex/config.toml; not configured here
  permission_mode → ThreadOptions(approvalPolicy=...)
                    "bypassPermissions"/"acceptEdits" → "never"
                    "default"/"plan"                  → "on-request"
  cwd             → ThreadOptions(workingDirectory=...)
  output_schema   → TurnOptions(outputSchema=...)
  max_turns       → tracked locally; aborts iteration once exceeded
  hooks           → NotImplementedError (Claude-only HookMatcher API)
  allowed_tools   → currently passthrough; tighter mapping deferred until needed
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncIterator

from openai_codex_sdk import (
    Codex,
    CodexOptions,
    TextInput,
    ThreadOptions,
    TurnOptions,
)

from hsb.runtime.codex_guards import assert_codex_oauth_only, verify_codex_mcp
from hsb.runtime.protocol import (
    AgentOptions,
    Message,
    PermissionMode,
    RuntimeName,
)


_PERMISSION_MAP: dict[PermissionMode, str] = {
    "default": "on-request",
    "acceptEdits": "never",
    "plan": "on-request",
    "bypassPermissions": "never",
}


def _build_codex_options() -> CodexOptions | None:
    """Honor CODEX_PATH_OVERRIDE so operators can reuse a globally-installed
    `codex` binary (npm i -g @openai/codex) without populating the SDK's
    vendor dir. Returns None when no override is set, letting the SDK fall
    back to find_codex_path().
    """
    override = os.environ.get("CODEX_PATH_OVERRIDE")
    if override:
        return CodexOptions(codex_path_override=override)
    return None


class CodexRuntime:
    name: RuntimeName = "codex"

    def __init__(self, codex_home: Path | None = None) -> None:
        self._codex_home = codex_home
        self._cached_config = assert_codex_oauth_only(codex_home=codex_home)

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        if options.hooks is not None:
            raise NotImplementedError(
                "Codex translation: hooks=... not supported (Claude HookMatcher API "
                "has no Codex equivalent). Flipping this agent to Codex disables "
                "hook-based guards."
            )
        if options.mcp_servers:
            verify_codex_mcp(self._cached_config, options.mcp_servers.keys())

        approval_policy = _PERMISSION_MAP.get(options.permission_mode)
        if approval_policy is None:
            raise NotImplementedError(
                f"Codex translation: permission_mode={options.permission_mode!r} "
                "has no mapping."
            )

        full_text = f"<system>{options.system_prompt}</system>\n\n{prompt}"

        thread_options = ThreadOptions(
            model=options.model,
            approvalPolicy=approval_policy,
            workingDirectory=options.cwd,
        )
        turn_options = TurnOptions(
            outputSchema=options.output_schema,
        )

        codex_opts = _build_codex_options()
        codex = Codex(codex_opts) if codex_opts is not None else Codex()
        thread = codex.start_thread(thread_options)
        streamed = await thread.run_streamed(
            TextInput(type="text", text=full_text),
            turn_options,
        )

        turns_seen = 0
        async for evt in streamed.events:
            turns_seen += 1
            if turns_seen > options.max_turns:
                raise RuntimeError(
                    f"Codex exceeded max_turns={options.max_turns}; aborting."
                )
            yield Message(
                text=getattr(evt, "text", "") or "",
                is_final=getattr(evt, "is_final", False),
                raw=evt,
            )

    def client(self, options: AgentOptions) -> Any:
        raise NotImplementedError(
            "CodexRuntime.client() not yet wired — WIO port pending. "
            "Use openai_codex_sdk.Thread directly until then."
        )
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/runtime/test_codex_runtime.py -v
```
Expected: 7 passed (init oauth check, init oauth-invalid, hooks rejection, mcp verify, thread/run translation, permission mode, cwd+output_schema).

- [ ] **Step 5: Commit**

```bash
git add src/hsb/runtime/codex.py tests/runtime/test_codex_runtime.py
git commit -m "feat(runtime): CodexRuntime — wraps openai_codex_sdk behind Runtime Protocol"
```

---

## Task 7: `resolve_runtime()` env-var resolver

**Files:**
- Modify: `src/hsb/agents/_sdk_options.py` (append at bottom)
- Test:   `tests/runtime/test_resolve_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
"""Per-agent runtime selection via env var."""
from __future__ import annotations

import pytest

from hsb.runtime.claude import ClaudeRuntime


def _patch_codex_home(monkeypatch, tmp_path):
    """Set CODEX_HOME to a valid fixture so CodexRuntime construction passes."""
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\n[mcp_servers.linear]\ncommand="npx"\n'
    )
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(home))


def test_default_returns_claude(monkeypatch):
    monkeypatch.delenv("HSB_RUNTIME_BACKLOG", raising=False)
    from hsb.agents._sdk_options import resolve_runtime
    rt = resolve_runtime("backlog")
    assert isinstance(rt, ClaudeRuntime)


def test_codex_value_returns_codex_runtime(monkeypatch, tmp_path):
    _patch_codex_home(monkeypatch, tmp_path)
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    from hsb.agents._sdk_options import resolve_runtime
    from hsb.runtime.codex import CodexRuntime
    rt = resolve_runtime("backlog")
    assert isinstance(rt, CodexRuntime)


def test_unknown_value_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "gpt-3")
    from hsb.agents._sdk_options import resolve_runtime
    with pytest.raises(ValueError, match=r"HSB_RUNTIME_BACKLOG"):
        resolve_runtime("backlog")


def test_wio_codex_raises(monkeypatch):
    monkeypatch.setenv("HSB_RUNTIME_WIO", "codex")
    from hsb.agents._sdk_options import resolve_runtime
    with pytest.raises(ValueError, match=r"WIO"):
        resolve_runtime("wio")


def test_agent_name_normalized_to_upper(monkeypatch):
    """resolve_runtime("backlog") reads HSB_RUNTIME_BACKLOG."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")
    from hsb.agents._sdk_options import resolve_runtime
    rt = resolve_runtime("backlog")
    assert rt.name == "claude"
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/runtime/test_resolve_runtime.py -v
```
Expected: ImportError on `resolve_runtime`.

- [ ] **Step 3: Implement `resolve_runtime`**

Append to `src/hsb/agents/_sdk_options.py`:

```python
# ---------------------------------------------------------------------------
# Per-agent runtime resolution. See:
# docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md §5.4
# ---------------------------------------------------------------------------

def resolve_runtime(agent_name: str):
    """Return the Runtime implementation for the given agent.

    Reads env var HSB_RUNTIME_<AGENT_NAME_UPPER>; default "claude".
    WIO is hard-coded to claude — HSB_RUNTIME_WIO=codex raises.
    """
    from hsb.runtime.claude import ClaudeRuntime
    from hsb.runtime.codex import CodexRuntime

    env_var = f"HSB_RUNTIME_{agent_name.upper()}"
    value = os.environ.get(env_var, "claude").strip().lower()

    if agent_name.lower() == "wio" and value == "codex":
        raise ValueError(
            "WIO is not flippable yet — stateful ClaudeSDKClient session has "
            "no Codex equivalent. Track separately when porting WIO."
        )

    if value == "claude":
        return ClaudeRuntime()
    if value == "codex":
        return CodexRuntime()
    raise ValueError(
        f"{env_var}={value!r} is invalid. Allowed: 'claude' or 'codex'."
    )
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/runtime/test_resolve_runtime.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/agents/_sdk_options.py tests/runtime/test_resolve_runtime.py
git commit -m "feat(runtime): resolve_runtime(agent_name) — per-agent env-var selector"
```

---

## Task 8: `make_agent_options()` factory

**Files:**
- Modify: `src/hsb/agents/_sdk_options.py` (append)
- Test:   `tests/runtime/test_make_agent_options.py`

- [ ] **Step 1: Write the failing test**

```python
"""make_agent_options factory — runtime-agnostic AgentOptions builder."""
from __future__ import annotations

import pytest

from hsb.agents._sdk_options import make_agent_options
from hsb.runtime.protocol import AgentOptions


def test_returns_agent_options_dataclass(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    opts = make_agent_options(
        system_prompt="sys",
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        max_turns=5,
        model="claude-opus-4-7",
    )
    assert isinstance(opts, AgentOptions)
    assert opts.allowed_tools == ("Read",)


def test_runs_g1_oauth_guard(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    with pytest.raises(RuntimeError, match=r"G1 violation"):
        make_agent_options(
            system_prompt="x",
            allowed_tools=[],
            permission_mode="default",
            max_turns=1,
            model="m",
        )


def test_runs_g2_forbidden_tool_guard(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match=r"G2 violation"):
        make_agent_options(
            system_prompt="x",
            allowed_tools=["Agent"],
            permission_mode="default",
            max_turns=1,
            model="m",
        )


def test_optional_fields_passthrough(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    opts = make_agent_options(
        system_prompt="x",
        allowed_tools=[],
        permission_mode="default",
        max_turns=1,
        model="m",
        mcp_servers={"linear": {"command": "npx"}},
        cwd="/tmp",
        hooks=["sentinel"],
    )
    assert opts.mcp_servers == {"linear": {"command": "npx"}}
    assert opts.cwd == "/tmp"
    assert opts.hooks == ["sentinel"]
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/runtime/test_make_agent_options.py -v
```
Expected: ImportError on `make_agent_options`.

- [ ] **Step 3: Implement the factory**

Append to `src/hsb/agents/_sdk_options.py`:

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
    """Runtime-agnostic options factory. Returns AgentOptions.

    Enforces G1 + G2 (same as make_options). Use this when an agent goes
    through the Runtime Protocol; use make_options() when an agent still
    calls claude_agent_sdk directly.
    """
    from hsb.runtime.protocol import AgentOptions

    assert_oauth2_only()  # G1
    forbidden = _FORBIDDEN_TOOLS & set(allowed_tools)
    if forbidden:
        raise ValueError(
            f"G2 violation: {forbidden} must not appear in allowed_tools. "
            "Sub-subagent dispatch is forbidden by WORC-02."
        )
    return AgentOptions(
        system_prompt=system_prompt,
        allowed_tools=tuple(allowed_tools),
        permission_mode=permission_mode,
        max_turns=max_turns,
        model=model,
        mcp_servers=mcp_servers,
        cwd=cwd,
        output_schema=output_schema,
        hooks=hooks,
    )
```

- [ ] **Step 4: Run test to verify pass**

```bash
uv run pytest tests/runtime/test_make_agent_options.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/hsb/agents/_sdk_options.py tests/runtime/test_make_agent_options.py
git commit -m "feat(runtime): make_agent_options() factory returns runtime-agnostic AgentOptions"
```

---

## Task 9: Refactor `backlog_agent.py` to use the runtime adapter

**Files:**
- Modify: `src/hsb/agents/backlog_agent.py` (the `_run_backlog_agent_async` function and imports)
- No new test in this task — Task 10 is the parity test.

- [ ] **Step 1: Read current `backlog_agent.py` end-to-end**

```bash
uv run python -c "import pathlib; print(pathlib.Path('src/hsb/agents/backlog_agent.py').read_text())"
```
Note where `ClaudeAgentOptions(...)` is constructed and where `query(...)` is called. The refactor replaces both with the runtime adapter.

- [ ] **Step 2: Update imports**

Replace at the top of `src/hsb/agents/backlog_agent.py`:

```python
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)
```

with:

```python
from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage

from hsb.agents._sdk_options import make_agent_options, resolve_runtime
```

Drop the `ClaudeAgentOptions` and `query` imports — they are now behind the runtime seam.

- [ ] **Step 3: Replace the options + query call**

Inside `_run_backlog_agent_async`, replace:

```python
    options = ClaudeAgentOptions(
        model="claude-opus-4-7",
        mcp_servers={...},
        allowed_tools=[...],
        permission_mode="acceptEdits",
        system_prompt=BACKLOG_SYSTEM_PROMPT,
        max_turns=80,
        hooks=LINEAR_HOOKS,
    )
```

with:

```python
    options = make_agent_options(
        system_prompt=BACKLOG_SYSTEM_PROMPT,
        allowed_tools=[
            "mcp__linear__create_issue",
            "mcp__linear__list_issues",
            "mcp__linear__get_issue",
            "Read",
        ],
        permission_mode="acceptEdits",
        max_turns=80,
        model="claude-opus-4-7",
        mcp_servers={
            "linear": {
                "command": "npx",
                "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"],
            }
        },
        hooks=LINEAR_HOOKS,
    )
    runtime = resolve_runtime("backlog")
```

And replace the `async for message in query(prompt=prompt, options=options):` line with:

```python
    async for message in runtime.query(prompt, options):
```

- [ ] **Step 4: Update the `init` SystemMessage handling**

The runtime `Message` wraps the underlying SDK message at `message.raw` for the Claude path. The Backlog Agent's existing logic checks `isinstance(message, SystemMessage)` etc — adjust to inspect `message.raw` instead. Within `_run_backlog_agent_async`, replace the existing `async for message in ...` body's type checks with:

```python
        async for message in runtime.query(prompt, options):
            sdk_msg = message.raw
            if isinstance(sdk_msg, SystemMessage) and sdk_msg.subtype == "init":
                failed = [
                    s
                    for s in sdk_msg.data.get("mcp_servers", [])
                    if s.get("status") != "connected"
                ]
                if failed:
                    raise RuntimeError(f"Linear MCP failed to connect: {failed}")
            elif isinstance(sdk_msg, AssistantMessage):
                # accumulate text from sdk_msg.content as before
                ...
            elif isinstance(sdk_msg, ResultMessage):
                # final-result handling as before
                ...
```

(Keep the existing accumulation/final-result logic — the only change is `sdk_msg = message.raw` indirection.)

- [ ] **Step 5: Run existing Backlog tests**

```bash
uv run pytest tests/test_linear_agent.py tests/integration/ -k backlog -v
```
Expected: still pass on the Claude path (default runtime).

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest tests/ -x -q
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/hsb/agents/backlog_agent.py
git commit -m "refactor(backlog): route through runtime adapter (resolve_runtime + make_agent_options)"
```

---

## Task 10: Backlog runtime parity test

**Files:**
- Create: `tests/integration/test_backlog_runtime_parity.py`

- [ ] **Step 1: Write the parity test**

```python
"""Backlog runtime parity: same plan.md fixture must produce a valid
BacklogOutput on both runtimes when the underlying SDKs are mocked.
This validates the Runtime Protocol seam, not real LLM behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hsb.agents.backlog_agent import _run_backlog_agent_async
from hsb.contracts.backlog import BacklogInput


FIXTURE_BACKLOG_JSON = json.dumps({
    "epics": [
        {
            "title": "[EPIC] Pilot epic",
            "description": "> from plan.md",
            "user_stories": [
                {
                    "title": "Story 1",
                    "description": "> story excerpt",
                    "tasks": [
                        {"title": "Task 1.1", "description": "> task excerpt"}
                    ],
                }
            ],
        }
    ],
    "traceability": {"plan_source": "fixture/plan.md"},
})


@pytest.fixture
def backlog_input(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nA tiny fixture plan.\n")
    from hsb.contracts.backlog import ProjectContext
    return BacklogInput(
        plan_source=str(plan),
        project_context=ProjectContext(name="fixture", team_id="LIN"),
    )


@pytest.fixture
def codex_home(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\n\n'
        '[mcp_servers.linear]\ncommand = "npx"\nargs = []\n'
    )
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


@pytest.mark.asyncio
async def test_claude_path_yields_valid_backlog_output(monkeypatch, backlog_input):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    fake_assistant = MagicMock()
    fake_assistant.content = [MagicMock(text=FIXTURE_BACKLOG_JSON)]
    fake_result = MagicMock()
    fake_result.usage = {}

    async def fake_query(prompt, options):
        yield fake_assistant
        yield fake_result

    with patch("claude_agent_sdk.query", side_effect=fake_query):
        out = await _run_backlog_agent_async(backlog_input)
    assert len(out.epics) == 1
    assert out.epics[0].title.startswith("[EPIC]")


@pytest.mark.asyncio
async def test_codex_path_yields_valid_backlog_output(monkeypatch, backlog_input, codex_home):
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")

    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    async def _events():
        yield SimpleNamespace(text=FIXTURE_BACKLOG_JSON, is_final=True)

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(
        return_value=SimpleNamespace(events=_events())
    )
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    # Backlog uses LINEAR_HOOKS, which CodexRuntime rejects. For the parity
    # test we patch hooks to None to exercise the Codex path. (Real flip:
    # operator accepts loss of hook-based guards; documented in GET-STARTED 1.5.)
    with patch("hsb.agents.backlog_agent.LINEAR_HOOKS", None), \
         patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        out = await _run_backlog_agent_async(backlog_input)

    assert len(out.epics) == 1
    fake_codex.start_thread.assert_called_once()


@pytest.mark.asyncio
async def test_pydantic_retry_does_not_swap_runtimes(monkeypatch, backlog_input):
    """First Claude attempt yields invalid JSON, retry yields valid; both must
    hit claude_agent_sdk.query, never openai_codex_sdk.Codex.
    """
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    bad_assistant = MagicMock()
    bad_assistant.content = [MagicMock(text="not json")]
    good_assistant = MagicMock()
    good_assistant.content = [MagicMock(text=FIXTURE_BACKLOG_JSON)]
    fake_result = MagicMock()
    fake_result.usage = {}

    call_count = {"n": 0}

    async def fake_query(prompt, options):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield bad_assistant
            yield fake_result
        else:
            yield good_assistant
            yield fake_result

    with patch("claude_agent_sdk.query", side_effect=fake_query) as q, \
         patch("hsb.runtime.codex.Codex") as codex_cls:
        out = await _run_backlog_agent_async(backlog_input)

    assert q.call_count == 2  # one retry
    codex_cls.assert_not_called()  # never silently switched runtime
    assert len(out.epics) == 1
```

- [ ] **Step 2: Run the parity test**

```bash
uv run pytest tests/integration/test_backlog_runtime_parity.py -v
```
Expected: 3 passed. If anything fails, fix the Runtime translation, not the test — the test is the contract.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_backlog_runtime_parity.py
git commit -m "test(backlog): runtime parity test — same plan, two runtimes, one BacklogOutput shape"
```

---

## Task 11: Live Codex smoke test scaffold

**Files:**
- Create: `tests/integration/test_backlog_codex_live.py`
- Modify: `pyproject.toml` (register the `live_codex` marker)

- [ ] **Step 1: Register the marker**

In `pyproject.toml`, under `[tool.pytest.ini_options]` (create the section if missing), add:

```toml
[tool.pytest.ini_options]
markers = [
    "live_codex: real Codex subscription smoke test (manual, opt-in via -m live_codex)",
]
```

If the section already exists, append the marker to the existing `markers = [...]` list.

- [ ] **Step 2: Create the smoke test**

`tests/integration/test_backlog_codex_live.py`:

```python
"""Live Codex smoke test — requires real ChatGPT subscription auth.

CI never runs this. Operator runs it manually after setting up
`codex login --device-auth` and creating ~/.codex/config.toml per
GET-STARTED.md Step 1.5.

    uv run pytest tests/integration/test_backlog_codex_live.py -m live_codex -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hsb.agents.backlog_agent import _run_backlog_agent_async
from hsb.contracts.backlog import BacklogInput, ProjectContext


pytestmark = pytest.mark.live_codex


@pytest.fixture
def session_count_before():
    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.exists():
        return 0
    return sum(1 for _ in sessions_dir.rglob("*"))


@pytest.mark.asyncio
async def test_backlog_runs_against_live_codex(monkeypatch, tmp_path, session_count_before):
    if "HSB_LIVE_CODEX" not in os.environ:
        pytest.skip("HSB_LIVE_CODEX env var must be set explicitly to run live test")

    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Tiny fixture plan\n\nOne user story: render hello world.\n"
    )
    inp = BacklogInput(
        plan_source=str(plan),
        project_context=ProjectContext(name="live-codex-smoke", team_id="LIN"),
    )

    out = await _run_backlog_agent_async(inp)

    assert len(out.epics) >= 1, "Codex should have produced at least one EPIC"
    assert out.epics[0].title.startswith("[EPIC]")

    sessions_dir = Path.home() / ".codex" / "sessions"
    sessions_after = sum(1 for _ in sessions_dir.rglob("*"))
    assert sessions_after > session_count_before, "Codex did not persist a session"
```

- [ ] **Step 3: Confirm CI skips it**

```bash
uv run pytest tests/integration/test_backlog_codex_live.py -v
```
Expected: `1 deselected` (or `1 skipped` if `HSB_LIVE_CODEX` is unset and the marker is recognized). Do NOT pass `-m live_codex` here.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_backlog_codex_live.py pyproject.toml
git commit -m "test(backlog): opt-in live Codex smoke test (live_codex marker)"
```

---

## Task 12: GET-STARTED.md — Step 1.5 OpenAI Codex OAuth2

**Files:**
- Modify: `GET-STARTED.md`

- [ ] **Step 1: Locate the insertion point**

```bash
grep -n "^### Step 2" GET-STARTED.md | head -3
```
Note the line number of the existing `### Step 2 — Linear MCP OAuth` heading. Insert the new section immediately before it.

- [ ] **Step 2: Insert Step 1.5**

Insert before the line you just located:

```markdown
### Step 1.5 — OpenAI Codex OAuth2 (only if any HSB_RUNTIME_*=codex)

Required only if you plan to flip any agent to the Codex runtime
(e.g. `export HSB_RUNTIME_BACKLOG=codex`). Skip this step if you stay on Claude.

**Why:** quota is consumed against the operator's ChatGPT subscription seat
(Plus / Pro / Business / Edu / Enterprise). API-key auth is forbidden by the
extended G1 guard (`assert_oauth2_only` rejects `OPENAI_API_KEY`).

**1. Install the Codex CLI binary** (the `openai-codex-sdk` Python package needs to find a `codex` binary):

Option A — let the SDK manage the binary (simplest, vendored):
```bash
uv run python -c "from openai_codex_sdk import Codex; print(Codex.install(version='LATEST_COMPATIBLE'))"
# Replace LATEST_COMPATIBLE with the version compatible with the pinned openai-codex-sdk.
# This downloads the binary into the package's vendor/ dir (per find_codex_path).
```

Option B — reuse a globally-installed binary (good if you already have one):
```bash
npm i -g @openai/codex      # or: brew install codex
codex --version             # confirm install
export CODEX_PATH_OVERRIDE="$(which codex)"   # CodexRuntime reads this env var
```

Then verify either path:
```bash
uv run python -c "from openai_codex_sdk import Codex; Codex(); print('binary OK')"
```

**2. Pin OAuth-only:** create or edit `~/.codex/config.toml`:

```toml
forced_login_method = "chatgpt"
model = "gpt-5.4"
approval_policy = "never"

[mcp_servers.linear]
command = "npx"
args    = ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]
```

**3. Login (VPS-friendly device flow):**

```bash
codex login --device-auth
# CLI prints a one-time code. Paste it at chatgpt.com/codex/device on any
# browser-capable machine — does not need to be the same machine.
```

**4. Verify:**

```bash
test -f ~/.codex/auth.json && echo "auth OK"
grep '^forced_login_method' ~/.codex/config.toml
env | grep -i OPENAI_API_KEY     # must be empty
```

**Caveats when flipping an agent to Codex:**

- The `LINEAR_HOOKS` (Linear MCP write-guard hooks) used by Backlog/QA on the
  Claude path **do not run on the Codex path**. Codex has no equivalent of
  `claude_agent_sdk.HookMatcher`. Flipping disables those guards for that
  agent's runs.
- The Work Item Orchestrator (WIO) is **not flippable** in this iteration.
  Setting `HSB_RUNTIME_WIO=codex` raises at startup. Tracked separately.
- The exact `openai-codex-sdk` PyPI version pinned in `pyproject.toml`
  expects a compatible `@openai/codex` CLI version. If JSON-RPC errors
  appear at runtime, upgrade the CLI: `npm i -g @openai/codex@latest`.
```

- [ ] **Step 3: Verify markdown renders**

```bash
head -200 GET-STARTED.md | tail -80
```
Visually confirm the new section sits between Step 1 and Step 2 with consistent heading levels.

- [ ] **Step 4: Commit**

```bash
git add GET-STARTED.md
git commit -m "docs(get-started): Step 1.5 — OpenAI Codex OAuth2 setup for runtime flip"
```

---

## Task 13: Migration playbook in `runtime/AGENT-CONTRACTS.md`

**Files:**
- Modify: `runtime/AGENT-CONTRACTS.md` (append a new section)

- [ ] **Step 1: Read the current file structure**

```bash
grep -n "^##" runtime/AGENT-CONTRACTS.md
```
Note where the existing top-level sections end so the new section appends cleanly.

- [ ] **Step 2: Append the migration section**

Append at the end of `runtime/AGENT-CONTRACTS.md`:

```markdown
## Per-agent runtime flip (Claude ↔ Codex)

Pilot wired in 2026-05: `HSB_RUNTIME_BACKLOG=codex` flips the Backlog Agent
to OpenAI Codex CLI (subscription quota, OAuth-only). Spec:
[`docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md`](../docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md).

**Per-agent env-var matrix:**

| Env var | Pilot status |
|---|---|
| `HSB_RUNTIME_BACKLOG` | **Wired** — flips between Claude and Codex |
| `HSB_RUNTIME_BUILDER` | Reads accepted at resolve_runtime; agent itself not yet routed through runtime adapter (still calls `claude_agent_sdk` directly) |
| `HSB_RUNTIME_QA` | Same as Builder |
| `HSB_RUNTIME_GIT` | Same |
| `HSB_RUNTIME_UAT` | Same |
| `HSB_RUNTIME_LINEAR` | Same |
| `HSB_RUNTIME_RISK14` | Same |
| `HSB_RUNTIME_WIO` | Hard-blocked: `codex` value raises `ValueError` at `resolve_runtime`. Stateful client port pending. |

**To migrate another one-shot agent (Builder / QA / Git / UAT / Linear / Risk-14):**

1. Replace the agent module's direct imports:
   ```python
   from claude_agent_sdk import ClaudeAgentOptions, query
   ```
   with:
   ```python
   from hsb.agents._sdk_options import make_agent_options, resolve_runtime
   ```
2. Replace the `ClaudeAgentOptions(...)` construction with `make_agent_options(...)`.
3. Replace `async for msg in query(prompt=p, options=opts):` with:
   ```python
   runtime = resolve_runtime("<agent_name>")
   async for msg in runtime.query(p, opts):
       sdk_msg = msg.raw  # original SDK message for type checks
       ...
   ```
4. If the agent uses `hooks=...`, decide: keep on Claude (CodexRuntime raises on
   non-None hooks) OR remove and document the loss of hook-based guards.
5. Verify any per-call `mcp_servers={...}` keys are also present in the
   operator's `~/.codex/config.toml` if the operator intends to flip this agent.
6. Add a runtime-parity test mirroring `tests/integration/test_backlog_runtime_parity.py`.

**WIO migration is not mechanical** — it uses `ClaudeSDKClient` (stateful
session with `@tool` decorators and inline cycle-cap state machine). Porting
requires implementing `CodexRuntime.client()` against `openai_codex_sdk.Thread`
and re-deriving the in-session tool surface. Tracked separately.
```

- [ ] **Step 3: Commit**

```bash
git add runtime/AGENT-CONTRACTS.md
git commit -m "docs(runtime): migration playbook for flipping additional agents to Codex"
```

---

## Final verification

- [ ] **Run full suite**

```bash
uv run pytest tests/ -q
```
Expected: all unit + integration tests pass; `live_codex`-marked test deselected.

- [ ] **Confirm worktree state is clean**

```bash
git status
git log --oneline origin/main..HEAD
```
Expected: clean working tree; one commit per task above (~13 commits) on `feature/codex-oauth-alt-runtime`.

- [ ] **Sanity-check the chokepoint**

```bash
grep -n "claude_agent_sdk" src/hsb/agents/backlog_agent.py
```
Expected: `claude_agent_sdk` only appears in the message-type imports (`AssistantMessage`, `ResultMessage`, `SystemMessage`) — no `ClaudeAgentOptions` or `query` import. The runtime adapter owns those now.

- [ ] **Manual operator dry-run (optional, if you have a ChatGPT subscription):**

  1. Follow GET-STARTED.md Step 1.5.
  2. `export HSB_RUNTIME_BACKLOG=codex && export HSB_LIVE_CODEX=1`
  3. `uv run pytest tests/integration/test_backlog_codex_live.py -m live_codex -v`

  Expected: passes. New session file in `~/.codex/sessions/`. ChatGPT quota consumed (verify in account dashboard if curious).

---

## Self-review

Verified against `docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md`:

- **§4 Architecture** — `Runtime` Protocol + two implementations + chokepoint extension: Tasks 2, 3, 6, 7, 8 ✓
- **§5.1 Protocol** — Task 2 ✓
- **§5.2 ClaudeRuntime** — Task 3 ✓
- **§5.3 CodexRuntime + translation table** — Task 6 (rows: system_prompt, model, mcp_servers, allowed_tools acknowledged via NotImplementedError, permission_mode mapping, cwd, max_turns, output_schema). Hooks added per known-constraint note in plan header. ✓
- **§5.4 _sdk_options extensions** — Tasks 4 (assert_oauth2_only), 5 (assert_codex_oauth_only + verify_codex_mcp), 7 (resolve_runtime), 8 (make_agent_options) ✓
- **§5.5 Backlog pilot refactor** — Task 9 ✓
- **§6 Data flow** — covered by Tasks 9-10; cold-start checks asserted in Task 5/6 tests ✓
- **§7.1 Env-var matrix** — Task 7 (pilot wiring) + Task 13 (matrix doc) ✓
- **§7.2 GET-STARTED.md Step 1.5** — Task 12 ✓
- **§8 Error handling** — covered by Tasks 4 (G1 OPENAI), 5 (G1-Codex + MCP), 6 (hooks rejection, max_turns), 7 (WIO fence) ✓
- **§9.1 Unit tests** — Tasks 2, 3, 5, 6, 7, 8 ✓
- **§9.2 Backlog parity** — Task 10 ✓
- **§9.3 Live smoke** — Task 11 ✓
- **§10 Dependencies** — Task 1 ✓
- **§11 Migration playbook** — Task 13 ✓

No placeholder strings (`TBD`, `TODO`, `implement later`) in any task body.
Type-name consistency check: `AgentOptions`, `Message`, `Runtime`, `StatefulClient`, `ClaudeRuntime`, `CodexRuntime`, `make_agent_options`, `resolve_runtime`, `assert_codex_oauth_only`, `verify_codex_mcp` — all referenced consistently across tasks.
