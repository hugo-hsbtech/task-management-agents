# Phase 4: Global + Main Orchestrators and Parallel Mode - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 04-global-main-orchestrators-and-parallel-mode
**Areas discussed:** Orchestrator implementation, Parallel claiming field, Worktree spawning mechanism, CLI evolution

---

## Orchestrator Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Pure Python dispatch | Both orchestrators as Python functions/classes calling Linear MCP directly. No LLM reasoning. | ✓ |
| Both as Agent SDK sessions | Same pattern as WIO — Claude Agent SDK sessions with skill specs injected | |
| Hybrid: Python Global, Agent Main | Global = pure Python, Main = Agent SDK session | |

**User's choice:** Pure Python dispatch for both  
**Notes:** User confirmed OAuth2 applies to all integrations (not just Linear). Pure Python is acceptable as long as all integration calls stay within the OAuth2-authenticated MCP tool layer. WIO remains the only Agent SDK session.

---

## Parallel Claiming Field

| Option | Description | Selected |
|--------|-------------|----------|
| Custom Linear field | Pre-configure 'assigned_orchestrator' text field; agent writes execution_id and verifies | |
| Status + updatedAt timestamp | Optimistic lock via pre/post write timestamp comparison; no Linear config needed | ✓ |
| Structured comment marker | Post '[CLAIMED:execution_id]' comment; re-read most recent comment to verify | |

**User's choice:** Status + updatedAt optimistic locking  
**Notes:** User initially asked about custom field creation via agent API — that path requires raw GraphQL calls with API key/token management outside OAuth2 MCP layer, which is ruled out by architectural constraint. Hard rule confirmed: no API keys for any integration, ever. OAuth2 only. Custom field approach rejected on that basis.

---

## Worktree Spawning Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Python creates worktrees + subprocess WIOs | `git worktree add` per task + subprocess per WIO + asyncio.gather() | ✓ |
| asyncio.gather() in-process, no worktrees | Concurrent Agent SDK sessions sharing working directory — violates MORD-04 | |

**User's choice:** Python creates worktrees + subprocess WIOs  
**Notes:** Clear preference for MORD-04 compliance. `isolation: worktree` is a Claude Code Task() feature not available as a Python API, so Python-native `git worktree` + subprocess is the correct implementation path.

---

## CLI Evolution

| Option | Description | Selected |
|--------|-------------|----------|
| New command + keep old | `hsb run` (new); `hsb run-next-step` retained for debugging | ✓ |
| Upgrade run-next-step in place | Replace internals, add --mode flag, lose direct-WIO debug path | |
| Mode as config, not flag | Read mode from `.hsb/config.toml`; no per-run flag | |

**User's choice:** New `hsb run` command, retain `hsb run-next-step`

| Default mode option | Description | Selected |
|--------------------|-------------|----------|
| Default cascade, explicit --parallel | Safe default; parallel requires explicit opt-in | ✓ |
| Always require --mode flag | Forces explicit mode every invocation | |

**User's choice:** Default cascade, `--parallel` flag to enable parallel mode  
**Notes:** Consistent with "start controlled" principle established in Phase 3. Parallel mode never activates accidentally.

---

## Claude's Discretion

- Worktree path gitignore strategy
- Subprocess WIO interface (env vars vs JSON file vs stdin)
- Global Orchestrator priority sort key
- SKILL.md migration for `skills/00-MAIN-ORCHESTRATOR.md` and `skills/07-GLOBAL-ORCHESTRATION.md`

## Deferred Ideas

- Custom Linear `assigned_orchestrator` field — requires API key path, ruled out permanently
- Multi-process parallel dispatch locking — deferred to future scope
- Event-driven mode — v2 scope
