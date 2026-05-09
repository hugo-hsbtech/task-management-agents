# HSBTech Agent Contracts

This file documents inter-agent contracts: capability boundaries, status
transitions, and operational concerns that span more than one agent class.

> Note: this file was created in `feature/codex-oauth-alt-runtime` and
> currently contains only the per-agent runtime-flip playbook. Other
> contract documentation may be merged in from sibling branches as the
> milestone consolidates.

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
(with `Thread.run_streamed(...)` for multi-turn) and re-deriving the `@tool`
surface. Tracked separately.
