# Codex as an Alternative OAuth2 Runtime — Design

**Date:** 2026-05-09
**Status:** Spec — pending implementation plan
**Branch:** `feature/codex-oauth-alt-runtime` (worktree off `origin/main`)
**Pilot agent:** Backlog Agent

---

## 1. Goal

Allow individual HSBTech agents to run on the OpenAI Codex CLI runtime instead of Claude Code, selectable per agent via environment variable. Auth on both runtimes is OAuth2 only — quota is consumed against the operator's ChatGPT subscription seat (Plus/Pro/Business/Edu/Enterprise), never against a metered API key. Pilot ships flippability for the **Backlog Agent**; the architecture is built so any other one-shot `query()`-pattern agent can be flipped later by replacing one import and one env-var read.

## 2. Non-goals

- **Stateful agents (Work Item Orchestrator).** The current Claude path uses `ClaudeSDKClient` (multi-turn session with `@tool` decorators and hooks). Codex's parallel `Thread` API exists but porting WIO requires re-deriving the in-session tool surface and the cycle-cap state machine. Out of scope; the Protocol exposes a `client()` method so a future port is mechanical.
- **Mixed-runtime within one agent run.** An agent picks one runtime per invocation; we do not split a single run across two runtimes.
- **Silent fallback.** If the operator chose Codex and Codex fails, the agent fails. No fallback to Claude — that would hide quota leaks and break reproducibility.
- **Cross-runtime golden text equality.** Codex and Claude won't produce byte-identical outputs; pydantic schema parity is the contract, not text parity.
- **Replacing `claude_agent_sdk` for Claude-side agents.** Claude path is unchanged structurally — it just moves behind the `Runtime` Protocol seam.

## 3. Context

The project's PROJECT.md mandates "tool-agnostic agent design (no hard dependency on Claude Code vs. Codex)" and lists "Skills as markdown specs — runtime-agnostic; works with Claude Code, Codex, and future runtimes" as a pending decision. STACK.md endorses using *the native SDK for the runtime you're targeting* (claude-agent-sdk for Claude) and explicitly forbids third-party agent frameworks layered on top (LangChain, CrewAI, AutoGen). The Codex equivalent — `openai-codex-sdk` — is the official OpenAI SDK for the Codex runtime and is the symmetric counterpart to claude-agent-sdk; using it does not violate the STACK.md spirit.

Today every agent imports `claude_agent_sdk` directly. Auth is gated by `assert_oauth2_only()` in `src/hsb/agents/_sdk_options.py`, which rejects `ANTHROPIC_API_KEY` and expects `CLAUDE_CODE_OAUTH_TOKEN` (set via `claude setup-token`). All `ClaudeAgentOptions` construction goes through the `make_options()` chokepoint where G1 + G2 guards live.

## 4. Architecture

A new `src/hsb/runtime/` package introduces a `Runtime` Protocol and two implementations. Agents stop importing `claude_agent_sdk` directly; they import the resolved runtime instead. Pure-Python agents (Main Orchestrator, Global Orchestrator, Risk skills 12/13) are untouched.

```
┌──────────────────────────────────────────────────────────────┐
│  agent code (e.g. backlog_agent.py)                          │
│  ─────────────────────────────────────                        │
│  rt = resolve_runtime("backlog")          ← env-var lookup   │
│  options = make_options(...)              ← G1 + G2 guards   │
│  async for msg in rt.query(prompt, options): ...             │
└─────────────────────────┬────────────────────────────────────┘
                          │
            ┌─────────────┴──────────────┐
            ▼                            ▼
┌────────────────────────┐  ┌────────────────────────────┐
│  ClaudeRuntime         │  │  CodexRuntime              │
│  ───────────           │  │  ────────────              │
│  claude_agent_sdk      │  │  openai_codex_sdk          │
│  .query / .Client      │  │  .Codex / .Thread          │
│  → Claude Code binary  │  │  → codex CLI binary        │
│  → CLAUDE_CODE_OAUTH   │  │  → ~/.codex/auth.json      │
└────────────────────────┘  └────────────────────────────┘
```

Three invariants:
1. The G1/G2 guards stay in `_sdk_options.py` and remain the single enforcement point.
2. Agent class structure (Backlog, Builder, QA, etc.) is unchanged.
3. The agent-facing API surface (`make_options(...)`, the message-iteration shape) does not change.

## 5. Components

### 5.1 `src/hsb/runtime/protocol.py`

```python
from typing import Protocol, AsyncIterator, Literal
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentOptions:
    """Runtime-agnostic option shape. Returned by make_options()."""
    system_prompt: str
    allowed_tools: tuple[str, ...]
    permission_mode: Literal["never", "acceptAll", "untrusted"]
    max_turns: int
    model: str
    mcp_servers: dict[str, dict] | None = None
    cwd: str | None = None
    output_schema: dict | None = None  # JSON Schema for structured output

class Runtime(Protocol):
    name: Literal["claude", "codex"]
    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator["Message"]: ...
    def client(self, options: AgentOptions) -> "StatefulClient": ...  # for future WIO port
```

`Message` and `StatefulClient` are defined in the same module and minimally mirror the surface area Backlog needs (text content, result message with usage). They are NOT a re-export of `claude_agent_sdk.Message` — they're the lowest common denominator.

### 5.2 `src/hsb/runtime/claude.py` — `ClaudeRuntime`

Translates `AgentOptions` → `claude_agent_sdk.ClaudeAgentOptions`, calls `claude_agent_sdk.query(...)`, yields messages. Pure passthrough — no behavioral change vs today.

### 5.3 `src/hsb/runtime/codex.py` — `CodexRuntime`

Wraps `openai_codex_sdk.Codex` (PyPI: `openai-codex-sdk` v0.1.11+, official OpenAI). Translation table for the Backlog-required option subset:

| `AgentOptions` field | Codex-side handling |
|---|---|
| `system_prompt` | Prepended to the prompt as `<system>...</system>` block, wrapped in `TextInput(type="text", text=...)`. Codex has no `system_prompt` kwarg. |
| `model` | `ThreadOptions(model=...)`, passed to `codex.start_thread(...)`. |
| `mcp_servers` | **Verified** (not configured) at startup against `~/.codex/config.toml`; mismatch → fail-fast. Codex MCP config is operator-managed via TOML. |
| `allowed_tools` | Mapped to `ThreadOptions.sandboxMode` (`"read-only"` if all tools are read-only; `"workspace-write"` otherwise) and per-MCP approval rules in operator's TOML. `NotImplementedError` for unmappable cases. |
| `permission_mode` | `ThreadOptions.approvalPolicy`: `"acceptEdits"`/`"bypassPermissions"` → `"never"`; `"default"`/`"plan"` → `"on-request"`. Codex's `"untrusted"` and `"on-failure"` values reachable via raw passthrough if needed later. |
| `cwd` | `ThreadOptions.workingDirectory`. |
| `max_turns` | Codex has no equivalent flag; tracked in adapter, aborts the iteration once exceeded. |
| `output_schema` | `TurnOptions.outputSchema`, passed to `await thread.run_streamed(...)`. Codex validates the final response against the JSON Schema. |

Pydantic 3-retry self-correction (today's logic in `backlog_agent.py`) stays in place. On the Codex path the first attempt is *also* validated by Codex's `output_schema` flag, so the retry layer triggers less often, but the surface stays identical.

### 5.4 `src/hsb/agents/_sdk_options.py` — extensions

- `assert_oauth2_only()` extended: also rejects `OPENAI_API_KEY`. Error message names both forbidden vars.
- New `assert_codex_oauth_only()`: reads and parses `~/.codex/config.toml`, requires `forced_login_method = "chatgpt"`, requires `~/.codex/auth.json` to exist (operator ran `codex login --device-auth`). Returns the parsed config dict so the caller can cache it. Called from `CodexRuntime.__init__` exactly once per process.
- New `verify_codex_mcp(parsed_config: dict, requested_servers: Iterable[str]) -> None`: for each requested MCP server name, asserts a `[mcp_servers.<name>]` block is present in the parsed config. Called from `CodexRuntime.query()` against the cached parsed config — cheap per-call check, no re-read of disk.
- New `resolve_runtime(agent_name: str) -> Runtime`: reads env var `HSB_RUNTIME_<AGENT_NAME_UPPER>`. Default `claude`. WIO is hard-coded to claude — `HSB_RUNTIME_WIO=codex` raises `ValueError("WIO not flippable yet — stateful client not ported")`.

### 5.5 `src/hsb/agents/backlog_agent.py` — pilot refactor

Two-line change at the call site:
```python
# before:
from claude_agent_sdk import query
...
async for msg in query(prompt=p, options=opts): ...

# after:
from hsb.agents._sdk_options import resolve_runtime
runtime = resolve_runtime("backlog")
async for msg in runtime.query(p, opts): ...
```
`make_options()` now returns `AgentOptions` (the runtime-agnostic dataclass). Both runtimes accept it. Builder/QA/Git/UAT/Linear/Risk-14 stay on direct `claude_agent_sdk` imports — they migrate the day someone flips one.

## 6. Data flow

### 6.1 Cold-start checks (once per process)

1. `assert_oauth2_only()` runs at first `make_options()` call — rejects if `ANTHROPIC_API_KEY` OR `OPENAI_API_KEY` is set.
2. `resolve_runtime("backlog")` reads `HSB_RUNTIME_BACKLOG` and returns a `CodexRuntime` (or `ClaudeRuntime`).
3. `CodexRuntime.__init__` runs `assert_codex_oauth_only()` (forced_login_method + auth.json) and caches the parsed `~/.codex/config.toml`.
4. Per-call: `CodexRuntime.query()` runs `verify_codex_mcp(cached_config, options.mcp_servers.keys())` against the cached config — fails fast if any requested MCP server name has no matching `[mcp_servers.<name>]` block.
5. Failures raise immediately with remediation messages pointing to GET-STARTED.md Step 1.5. No quiet fallback.

### 6.2 Per-call flow (Backlog → BacklogOutput, Codex path)

```
backlog_agent.run_backlog(plan_md)
  ├─ render system prompt + user prompt
  ├─ options = make_agent_options(...)              [G1, G2 guards → AgentOptions]
  ├─ rt = resolve_runtime("backlog")                [returns CodexRuntime]
  └─ async for msg in rt.query(prompt, options):
        └─ CodexRuntime.query(prompt, options)
              ├─ codex = Codex(CodexOptions(...))   [resolves codex binary]
              ├─ thread = codex.start_thread(ThreadOptions(
              │     model=options.model,
              │     approvalPolicy="never",
              │     workingDirectory=options.cwd))
              ├─ streamed = await thread.run_streamed(
              │     TextInput(type="text",
              │               text=f"<system>{options.system_prompt}</system>\n\n{prompt}"),
              │     TurnOptions(outputSchema=options.output_schema))
              └─ async for evt in streamed.events:
                    yield translate_event(evt)      [ThreadEvent → Message]
  └─ pydantic validation on final text
        ├─ ok → return BacklogOutput
        └─ fail → re-prompt (same runtime), retry up to 3x
```

The Claude path has the same shape; `ClaudeRuntime.query(...)` calls `claude_agent_sdk.query(...)` and yields messages straight through.

### 6.3 Linear MCP

Today's per-call `mcp_servers=...` arg works for the Claude path. The Codex side reads MCP config from `~/.codex/config.toml`. The adapter therefore *verifies* the config matches what the agent declared and *fails fast* if not — operator owns the one-time TOML setup via GET-STARTED.md. The Linear MCP server itself manages OAuth tokens at `~/.mcp-auth/`; both runtimes share these.

## 7. Configuration

### 7.1 Per-agent runtime selection

| Env var | Values | Default | Pilot status |
|---|---|---|---|
| `HSB_RUNTIME_BACKLOG` | `claude` \| `codex` | `claude` | **Wired in this iteration** |
| `HSB_RUNTIME_BUILDER` | `claude` \| `codex` | `claude` | Reads accepted; `CodexRuntime` raises `NotImplementedError("agent not yet ported")` |
| `HSB_RUNTIME_QA` | `claude` \| `codex` | `claude` | Same |
| `HSB_RUNTIME_GIT` | `claude` \| `codex` | `claude` | Same |
| `HSB_RUNTIME_UAT` | `claude` \| `codex` | `claude` | Same |
| `HSB_RUNTIME_LINEAR` | `claude` \| `codex` | `claude` | Same |
| `HSB_RUNTIME_RISK14` | `claude` \| `codex` | `claude` | Same |
| `HSB_RUNTIME_WIO` | only `claude` accepted | `claude` | Raises if set to `codex` |

Flipping a future agent is one env var + a ~10-LOC call-site refactor. No registry, no plugin file, no agent factory. The seam is the Protocol; everything else is convention.

### 7.2 Codex-side OAuth setup (operator, one-time)

GET-STARTED.md grows a new **Step 1.5 — OpenAI Codex OAuth2** section, inserted after the existing Anthropic OAuth step. Required only if any `HSB_RUNTIME_*=codex` is set.

```text
1. Install Codex CLI:    npm i -g @openai/codex   (or: brew install codex)
2. Pin OAuth-only:       create/edit ~/.codex/config.toml:

       forced_login_method = "chatgpt"
       model = "gpt-5.4"
       approval_policy = "never"

       [mcp_servers.linear]
       command = "npx"
       args    = ["-y", "mcp-remote", "https://mcp.linear.app/mcp", "..."]

3. Login (VPS-friendly):  codex login --device-auth
                          → opens a code; paste at chatgpt.com/codex/device on any browser
4. Verify:                test -f ~/.codex/auth.json && echo OK
5. Confirm OAuth-only:    grep '^forced_login_method' ~/.codex/config.toml
6. Confirm no API key:    env | grep -i OPENAI_API_KEY     # must be empty
```

## 8. Error handling

| # | Failure | Where it fires | What user sees |
|---|---|---|---|
| 1 | `OPENAI_API_KEY` is set | `assert_oauth2_only()` at `make_options()` call | `RuntimeError: G1 violation: OPENAI_API_KEY is set — forbidden. Use 'codex login --device-auth' (OAuth-only).` |
| 2 | `~/.codex/config.toml` missing or `forced_login_method != "chatgpt"` | `assert_codex_oauth_only()` at `CodexRuntime.__init__` | `RuntimeError: G1-Codex violation: forced_login_method must be "chatgpt" in ~/.codex/config.toml. See GET-STARTED.md Step 1.5.` |
| 3 | `~/.codex/auth.json` missing (operator never logged in) | `CodexRuntime.__init__` | `RuntimeError: Codex not authenticated. Run: codex login --device-auth` |
| 4 | Linear MCP not in `~/.codex/config.toml` while `mcp_servers=...` is requested | `CodexRuntime.query()`, before subprocess spawn | `RuntimeError: Codex MCP missing: [mcp_servers.linear] block not found. See GET-STARTED.md Step 1.5.` |
| 5 | Operator sets `HSB_RUNTIME_WIO=codex` | `resolve_runtime("wio")` | `ValueError: WIO is not flippable yet — stateful ClaudeSDKClient session has no Codex equivalent.` |

**Quota exhaustion** propagates as `QuotaExceededError` from `codex_app_server`. The pydantic 3-retry wrapper detects this exception class and aborts immediately rather than re-prompting (retrying makes the bill worse without helping).

**Option-translation failures** raise `NotImplementedError("Codex translation: <option>=<value> not yet supported")` at `CodexRuntime.query()`. Fail-fast, never silent.

**No fallback to Claude on Codex failure.** Same blast-radius semantics as G1 today.

## 9. Testing

### 9.1 Unit (mocked, fast) — `tests/runtime/`

- `test_protocol.py` — round-trips an `AgentOptions` through both runtimes with mocked underlying SDKs; asserts both yield Protocol-shaped messages.
- `test_resolve_runtime.py` — env-var permutations, including `HSB_RUNTIME_WIO=codex` raising and missing-var → claude default.
- `test_codex_g1.py` — three guards (`OPENAI_API_KEY`, `forced_login_method`, `auth.json`) each asserted with tmp-path fixtures.
- `test_codex_translation.py` — translation-table cases including `NotImplementedError` on un-mappable options.

### 9.2 Backlog parity — `tests/agents/test_backlog_runtime_parity.py`

Same canned `plan.md` fixture, run twice — once with `HSB_RUNTIME_BACKLOG=claude` against a mocked `claude_agent_sdk.query`, once with `HSB_RUNTIME_BACKLOG=codex` against a mocked `codex_app_server.Codex`. Both must produce a `BacklogOutput` instance that pydantic-validates against the same schema. Pydantic 3-retry exercised on each runtime: simulate invalid first response → confirm retry on the **same** runtime, no quiet runtime-switch.

### 9.3 Live smoke (manual, opt-in) — `tests/agents/test_backlog_codex_live.py`

`@pytest.mark.live_codex` so CI never runs it. Single idempotent Backlog run against a fixture plan, real Codex subscription. Asserts: returns valid `BacklogOutput`, consumes <20,000 tokens (budget guard sized for a small fixture plan; revisit if Backlog's prompt grows), `~/.codex/sessions/` gains exactly one new session file.

### 9.4 What is not tested

- Cross-runtime *text* equality (schema parity is the contract, not byte equality).
- A Codex-side mock of every Claude SDK feature — only the surface Backlog actually uses.

## 10. Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ...existing...
    "openai-codex-sdk",   # Python 3.10+; provides openai_codex_sdk. Pin exact version in implementation plan.
]
```

The implementation plan is responsible for pinning the exact `openai-codex-sdk` version published at the time of writing it, and ensuring the corresponding `codex` CLI binary version is documented in GET-STARTED.md (the SDK uses a vendored binary discovered via `find_codex_path()` or via `CodexOptions.codex_path_override`; SDK ↔ binary JSON-RPC protocol must match).

External binary requirement: the operator either runs `Codex.install(version="...")` once to populate the SDK's vendor dir, or installs `@openai/codex` globally and points the SDK at it via `CodexOptions(codex_path_override=...)` / `CODEX_PATH_OVERRIDE` env var. GET-STARTED Step 1.5 documents both paths.

## 11. Migration of additional agents (post-pilot)

To flip any one-shot `query()`-pattern agent to be runtime-aware:
1. In the agent module, replace `from claude_agent_sdk import query` with `from hsb.agents._sdk_options import resolve_runtime`.
2. At the call site: `runtime = resolve_runtime("<agent_name>")`, then `runtime.query(...)`.
3. Verify the agent's `make_options()` arguments translate (consult the table in §5.3); add new translations if needed.
4. Add the agent's row to the `HSB_RUNTIME_<AGENT>` env-var table in this spec and in `runtime/AGENT-CONTRACTS.md`.
5. Add a Codex-mocked unit test mirroring the Claude one.

WIO requires additional work because it uses `ClaudeSDKClient` (stateful) — porting requires implementing `CodexRuntime.client()` against `openai_codex_sdk.Thread` (with `Thread.run_streamed(...)` for multi-turn) and re-deriving the `@tool` surface. Tracked separately.

## 12. Open questions resolved

- **Q:** Use `openai-codex-sdk` or raw `codex exec` subprocess? **A:** SDK — symmetric to claude-agent-sdk, native `output_schema`, paves path for future stateful agents.
- **Q:** Where does runtime selection live? **A:** Per-agent env var, no new config file.
- **Q:** Any silent fallback? **A:** No.
- **Q:** Should pure-Python orchestrators be touched? **A:** No — they don't call LLMs.
- **Q:** Pilot agent? **A:** Backlog (operator choice; lowest volume = lowest pilot risk).
