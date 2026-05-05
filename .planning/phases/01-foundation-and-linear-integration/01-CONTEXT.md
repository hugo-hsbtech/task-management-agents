# Phase 1: Foundation and Linear Integration - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the working foundation that every downstream agent depends on:
- Python project scaffold with correct package structure and dependency stack
- Verified Linear MCP connection authenticated via OAuth 2.1
- Pydantic contract validation layer matching the schemas in `agents/AGENT-CONTRACTS.md`
- Knowledge Store directory structure (`knowledge/` with category subdirectories)
- Linear Agent fully operational: create, update, link, comment, and retry with backoff

No orchestration logic, no Builder/QA/Git agents. Those are Phase 2+.

</domain>

<decisions>
## Implementation Decisions

### Linear MCP Authentication
- **D-01:** Use OAuth 2.1 interactive browser flow for Linear MCP authentication. The `mcp-remote` transport handles this via `npx -y mcp-remote https://mcp.linear.app/mcp`. No API key management required.
- **D-02:** Token refresh is handled automatically by `mcp-remote`. No custom re-auth code needed.

### Python Project Structure
- **D-03:** Use `src/hsb/` layout — a proper Python package under `src/`. Subdirectories: `agents/`, `contracts/`, `cli/`.
- **D-04:** Pydantic contract models live in `src/hsb/contracts/` with one file per agent (e.g., `linear.py`, `backlog.py`, `qa.py`) — mirrors the AGENT-CONTRACTS.md structure.
- **D-05:** Use `pyproject.toml` (not `requirements.txt`) for packaging, entry points, and dependency pins. This enables `pip install -e .` and named CLI entry points.

### Skill File Migration
- **D-06:** Migrate only the Linear System of Record skill in Phase 1. Create `.claude/skills/linear-system-of-record/SKILL.md` with proper SKILL.md frontmatter.
- **D-07:** Keep `skills/05-LINEAR-SYSTEM-OF-RECORD.md` in place as human-readable reference. The two files serve different purposes: one for SDK auto-discovery, one for documentation.
- **D-08:** Other skills (`skills/01-BACKLOG-PLANNING.md` through `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md`) are NOT migrated in Phase 1. Each skill migrates in its own phase when it becomes executable.

### Claude's Discretion
- **Linear verification testing:** Whether to verify Linear operations with live calls to a real workspace or mock at the MCP boundary — Claude decides the test approach that satisfies LINR acceptance criteria.
- **Knowledge Store initialization:** Auto-create `knowledge/` subdirectories on first run or as part of a setup script — Claude decides. Must result in directory structure matching FOUND-04.
- **SKILL.md frontmatter content:** Exact frontmatter fields for `.claude/skills/linear-system-of-record/SKILL.md` (model, allowed-tools, disable-model-invocation, arguments) — Claude decides based on STACK.md guidance.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Agent Contracts and Architecture
- `agents/AGENT-CONTRACTS.md` — JSON schemas for all agent input/output contracts; pydantic models MUST match these exactly
- `agents/AGENTS.md` — agent responsibilities and capability boundaries
- `runtime/RUNTIME-EXECUTION.md` — runtime execution model and session handling

### Linear Integration
- `skills/05-LINEAR-SYSTEM-OF-RECORD.md` — Linear skill behavioral spec; the SKILL.md at `.claude/skills/linear-system-of-record/SKILL.md` must derive from this
- `.planning/research/STACK.md` — exact Linear MCP setup commands, OAuth flow, confirmed tool names, library versions, and "Do NOT use" list

### Pitfalls and Constraints
- `.planning/research/PITFALLS.md` — critical failure modes; Phase 1 must not introduce patterns that cause Pitfall 1 (double-claim), Pitfall 2 (QA runaway), or Pitfall 4 (stale state)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agents/AGENT-CONTRACTS.md`: Complete JSON schemas for all 14 agent contracts. The pydantic models in `src/hsb/contracts/` must exactly mirror these — do not invent new fields.
- `skills/05-LINEAR-SYSTEM-OF-RECORD.md`: Full behavioral spec for the Linear Agent. Migrate this content (with frontmatter added) to `.claude/skills/linear-system-of-record/SKILL.md`.

### Established Patterns
- No Python code exists yet — greenfield implementation.
- All skills are currently plain markdown at `skills/` root. Phase 1 establishes the `.claude/skills/` pattern for Phase 2+ to follow.

### Integration Points
- The Linear MCP server exposes `mcp__linear__*` tools (confirmed: `create_issue`, `update_issue`, `get_issue`, `list_issues`, `create_comment`, `list_projects`, `list_teams`). The Linear Agent wraps these behind the pydantic-validated contract interface.
- `pyproject.toml` entry points should register at least one CLI command that exercises all Linear Agent operations (satisfying LINR-01 through LINR-05 acceptance criteria).

</code_context>

<specifics>
## Specific Ideas

- `src/hsb/` package name matches the project short name (HSBTech). Consistent naming reduces cognitive load across phases.
- STACK.md provides exact install commands and the MCP setup invocation — copy these verbatim into setup docs rather than paraphrasing.
- Linear MCP tool prefix in Python contexts: `mcp__linear__*` (not `mcp__claude_ai_Linear__*` which is the Claude.ai session prefix).

</specifics>

<deferred>
## Deferred Ideas

- Full skill migration for all 14 skills — deferred to their respective phases (Phase 2+)
- API key fallback for headless/CI Linear auth — not in Phase 1 scope; revisit if CI integration is needed
- `run_loop.py` CLI loop — Phase 3 scope; Phase 1 only builds the Linear Agent verification CLI

</deferred>

---

*Phase: 01-foundation-and-linear-integration*
*Context gathered: 2026-05-05*
