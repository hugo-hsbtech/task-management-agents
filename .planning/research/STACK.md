# Technology Stack

**Project:** HSBTech AI Engineering Workflow
**Researched:** 2026-05-05
**Overall confidence:** HIGH (all critical choices verified against official docs or first-party sources)

---

## Recommended Stack

### Agent Orchestration Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Claude Agent SDK (Python) | 0.1.73+ | Primary orchestration runtime for CLI loop mode | Official Anthropic SDK — same loop that powers Claude Code. `query()` async iterator, built-in tools (Read/Write/Edit/Bash/Glob/Grep), native MCP support, subagent definitions, hooks, session resumption. Python >=3.10. |
| Claude Code CLI | v2.1.32+ | Interactive / manual-assisted mode for MVP | Direct terminal session. Subagents via `Task` tool. Agent Teams (experimental) for parallel dispatch. Zero extra tooling. Same skill/command loading as SDK. |
| Python 3.12 | 3.12.x | Runtime for CLI loop and orchestration harness | Stable, type-annotated, asyncio-native. SDK requires >=3.10; 3.12 gives full structural pattern matching for contract routing. |

**Do NOT use:** LangChain, LangGraph, CrewAI, or AutoGen as the orchestration layer. The project uses Claude Code/Codex natively; layering a third-party agent framework introduces unnecessary abstraction, incompatible tool schemas, and vendor lock-in with no benefit. The Claude Agent SDK already provides the agent loop, tool execution, subagent dispatch, and hooks.

**Do NOT use:** Anthropic Client SDK (anthropic==*) for orchestration. The Client SDK requires you to implement your own tool loop. Use `claude-agent-sdk` which executes the loop autonomously.

---

### Multi-Agent Dispatch Pattern

| Pattern | When | Implementation |
|---------|------|----------------|
| Cascade (sequential) | MVP / manual-assisted mode | `async for message in query(prompt=skill_content, options=ClaudeAgentOptions(...))` — single await per cycle |
| Parallel dispatch | Parallel mode | `await asyncio.gather(*[run_work_item_orchestrator(item) for item in ready_items])` — one coroutine per Work Item Orchestrator |

The `asyncio.gather` primitive is the correct and sufficient tool for parallel dispatch. Each Work Item Orchestrator is an independent `query()` call with its own session context. No shared mutable state between coroutines — all coordination happens through Linear.

**Subagent definitions (Claude Agent SDK):** Define each specialized agent (Builder, Git, QA, etc.) as an `AgentDefinition` with scoped `tools` list. Pass them via `ClaudeAgentOptions(agents={...})`. The main orchestrator invokes them with the `Agent` tool in its allowed tools list.

**Session resumption:** Capture `session_id` from the `SystemMessage(subtype="init")` event to resume a Work Item Orchestrator across CLI loop cycles without losing context.

---

### Linear MCP Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Linear Official MCP Server | Current (hosted) | All Linear state reads/writes | Official, centrally hosted, OAuth 2.1. First-party support guarantees schema compatibility with Linear's data model. |
| mcp-remote | latest | Transport adapter for remote MCP | Required bridge: `npx -y mcp-remote https://mcp.linear.app/mcp`. Handles SSE/HTTP transport. |

**Setup command (in Claude Code):**
```bash
claude mcp add-json linear '{"command":"npx","args":["-y","mcp-remote","https://mcp.linear.app/mcp"]}'
```

**Setup in Agent SDK (Python):**
```python
ClaudeAgentOptions(
    mcp_servers={
        "linear": {"command": "npx", "args": ["-y", "mcp-remote", "https://mcp.linear.app/mcp"]}
    }
)
```

**Authentication:** OAuth 2.1 (interactive, one-time) for developer use. For headless/CI use, pass `Authorization: Bearer <api_key>` directly. Generate API key at Linear → Settings → Account → Security & Access.

**Available tool operations (confirmed):** `list_issues`, `get_issue`, `create_issue`, `update_issue`, `list_my_issues`, `list_projects`, `get_project`, `create_project`, `update_project`, `list_teams`, `get_team`, `list_users`, `get_user`, `create_comment`. The tool name prefix in MCP call context is `mcp__linear__*` (e.g., `mcp__linear__create_issue`).

**Do NOT use:** Community Linear MCP servers (`jerhadf/linear-mcp-server`, `tacticlaunch/mcp-linear`). These are unofficial implementations with partial coverage and no SLA. Linear's first-party server launched May 2025 and supersedes all community alternatives.

---

### GitHub / PR Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| GitHub CLI (`gh`) | 2.x+ | Branch creation, PR creation, PR diff retrieval | Native GitHub tooling. `gh pr create --base <epic-branch> --head <task-branch>` directly implements the stacked PR pattern. QA Agent reads `gh pr diff <number>` for review input. |
| `gh stack` (extension) | Current (private preview) | Stacked PR lifecycle management | Official GitHub extension for stacked PR workflows. `gh extension install github/gh-stack`. Handles cascading rebases and PR base targeting automatically. Currently in private preview — use `gh pr create --base` manually if `gh stack` is not available. |

**Stacked PR workflow without `gh stack`:**
1. `git checkout -b epic/LIN-100` (EPIC branch from main)
2. For each task: `git checkout -b feature/LIN-123-slug epic/LIN-100`
3. `gh pr create --base epic/LIN-100 --head feature/LIN-123-slug --title "[LIN-123] ..."` (task PR targets EPIC branch)
4. EPIC PR: `gh pr create --base main --head epic/LIN-100` (manual merge only)

**Do NOT use:** `hub` CLI (deprecated). Do not use GitHub API via `curl` directly — `gh` is the correct abstraction. Do not use any PR automation library that attempts automatic merges.

---

### Skills / Prompt Files (Runtime-Agnostic Agent Instructions)

| Technology | Format | Purpose | Why |
|------------|--------|---------|-----|
| SKILL.md (Agent Skills open standard) | YAML frontmatter + Markdown body | Define agent behavior in runtime-portable way | Supported by Claude Code, Codex, Cursor, and 30+ other runtimes. Frontmatter: `name`, `description`, optional `allowed-tools`, `model`, `context: fork`, `disable-model-invocation`. Progressive disclosure: only description loads at session start; full body loads on invocation. |

**Directory structure (project-scoped, committed to repo):**
```
.claude/skills/
  backlog-planning/SKILL.md
  implementation/SKILL.md
  qa-review/SKILL.md
  git-pr-management/SKILL.md
  linear-system-of-record/SKILL.md
  work-item-orchestration/SKILL.md
  global-orchestration/SKILL.md
  ...
```

Note: The project currently stores skills at `skills/` (root level, not `.claude/skills/`). For Claude Code and Agent SDK auto-discovery, skills must live at `.claude/skills/<name>/SKILL.md`. The existing `skills/` markdown files should be migrated to `.claude/skills/<name>/SKILL.md` with proper frontmatter added, OR kept at root as reference documents and referenced explicitly in skill content.

**Codex compatibility:** Codex discovers skills from `.agents/skills/` (not `.claude/skills/`). For full tool-agnostic portability, maintain skills in `.claude/skills/` as primary and add a `.agents/skills/` symlink or copy for Codex support.

**SKILL.md frontmatter fields used in this project:**
- `name`: matches skill directory name (e.g., `qa-review`)
- `description`: what the skill does + when to invoke — critical for auto-discovery
- `disable-model-invocation: true` for orchestrator-controlled skills (all skills except knowledge/enrichment)
- `allowed-tools`: pre-approve tools the skill needs (e.g., `Bash(git *) Bash(gh *)` for Git Agent)
- `context: fork` for skills that should run as isolated subagents
- `arguments`: named positional arguments for `$work_item_id` substitution

**Do NOT use:** Plain `.md` files at project root as the primary skill format. These work for human reference but bypass Claude's progressive disclosure loading, SKILL.md frontmatter features, and Codex/multi-runtime portability.

---

### File-Based Knowledge Store

| Technology | Format | Purpose | Why |
|------------|--------|---------|-----|
| Markdown files with YAML frontmatter | `.md` + `---` frontmatter | Persist reusable patterns, QA insights, architectural decisions | Git-native, human-readable, directly loadable by agent skills. No vector DB required for MVP. Linear holds operational state; knowledge store holds intelligence. |

**Directory layout:**
```
knowledge/
  architecture/
    <YYYY-MM-DD>-<slug>.md
  qa/
    <YYYY-MM-DD>-<slug>.md
  implementation/
    <YYYY-MM-DD>-<slug>.md
  patterns/
    <YYYY-MM-DD>-<slug>.md
  anti-patterns/
    <YYYY-MM-DD>-<slug>.md
  risk/
    <YYYY-MM-DD>-<slug>.md
```

**Frontmatter schema per entry:**
```yaml
---
title: string
type: architecture | qa | implementation | pattern | anti_pattern | risk
context: string (work item or EPIC slug)
evidence:
  linear_issue: LIN-123
  pr: url
date: YYYY-MM-DD
applicability: string
---
```

**Retrieval:** Intelligence Agent reads knowledge entries via `Glob` + `Grep` over `knowledge/` directory. No semantic search needed for MVP — category-based directory structure + date-sorted filenames provide sufficient discoverability.

**Do NOT use:** SQLite, vector databases (Chroma, Qdrant, Pinecone), or JSON files for the knowledge store at MVP stage. The file-based approach keeps state in git, eliminates infrastructure dependencies, and is directly consumable by LLM agents without tooling. Vector search is a Phase 2+ concern.

---

### Supporting Python Libraries

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `claude-agent-sdk` | 0.1.73+ | Agent loop, subagent dispatch, MCP, hooks | Primary SDK. `pip install claude-agent-sdk` |
| `asyncio` (stdlib) | 3.12 built-in | Parallel orchestrator dispatch | `asyncio.gather()` for parallel Work Item Orchestrators |
| `python-dotenv` | 1.0+ | `.env` file loading for `ANTHROPIC_API_KEY` etc. | `pip install python-dotenv` |
| `pydantic` | 2.x | JSON contract validation (agent input/output) | Validates the contract schemas defined in AGENT-CONTRACTS.md before dispatch |
| `typer` | 0.12+ | CLI interface for `run_loop.py` (`run next step`, `show state`, etc.) | `pip install typer`. Cleaner than argparse for the minimal runtime command set. |
| `rich` | 13.x | Terminal output formatting for runtime loop | Colored status output, progress, tables for `show current state` command |

**Do NOT use:** `click` (typer supersedes it with type annotations). Do not use `langchain` for any purpose. Do not use `httpx` or `requests` to call Linear directly — go through the MCP tool layer only.

---

### Runtime Loop (`run_loop.py`) Architecture

The CLI loop is a thin Python script — not a framework. Its sole job is to call the Main Orchestrator Agent via the Agent SDK, capture the result, and prompt the user for the next step.

```
run_loop.py
├── Command: run-next-step     → query(Main Orchestrator skill + current Linear state snapshot)
├── Command: show-state        → query(Global Orchestrator read-only, format output)
├── Command: show-next-action  → query(Global Orchestrator, return decision envelope only)
└── Command: run-action        → query(specific agent skill by action type)
```

**No persistent process required.** Each command is a standalone `asyncio.run()` call. State lives in Linear, not in the process. Session IDs are persisted to `.claude/session_cache.json` to enable resume across CLI invocations.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Orchestration SDK | `claude-agent-sdk` | LangGraph | Framework overhead, incompatible tool schema, unnecessary when target runtime is Claude Code |
| Orchestration SDK | `claude-agent-sdk` | OpenAI Agents SDK | Project is Claude Code / Codex — using the native SDK avoids model-switching friction and matches the SKILL.md format |
| Linear integration | Official Linear MCP | Community MCP servers | Unofficial, partial coverage, no schema guarantees, superseded by official server (May 2025) |
| Stacked PRs | `gh` CLI + `gh stack` | `git-stack`, `spr`, `ghstack` | `gh stack` is the official GitHub-native solution; others require extra installation and diverge from GitHub UI's stack map feature |
| Knowledge store | Flat markdown files | Chroma / Qdrant | Vector DB adds infra dependency with no clear benefit at MVP scale; file-based is git-native and directly readable by agents |
| Knowledge store | Flat markdown files | SQLite | Binary format, not git-diffable, requires SQL tooling in agent context |
| CLI loop | `typer` | `argparse` | typer gives type-annotated commands with auto-generated help for minimal effort |
| Parallel dispatch | `asyncio.gather` | Celery / Redis queues | Event-driven mode is out of scope for MVP; `asyncio.gather` is sufficient and zero-infra |
| Agent parallelism | Subagent definitions in SDK | Claude Code Agent Teams | Agent Teams are experimental, require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, have known limitations on session resumption. Use SDK subagents for production-grade parallel dispatch. |

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| Claude Agent SDK (Python) — version, APIs, import paths | HIGH | Official Anthropic docs (code.claude.com), PyPI page verified May 2026 |
| Claude Code subagent dispatch via `Task` tool | HIGH | Official Claude Code docs (code.claude.com/docs/en/agent-teams, sub-agents) |
| SKILL.md frontmatter — all fields, scopes, discovery paths | HIGH | Official Claude Code docs (code.claude.com/docs/en/skills) — full spec read |
| Linear MCP — official server, setup command, OAuth | HIGH | linear.app/docs/mcp, linear.app/changelog/2025-05-01-mcp |
| Linear MCP — exact tool name enumeration | MEDIUM | Community catalogs + official description. Official docs do not publish full tool list; community research found ~21 tools including create_issue, update_issue, list_issues |
| `gh` CLI stacked PR pattern | HIGH | Official GitHub docs (github.github.com/gh-stack) |
| `gh stack` extension availability | MEDIUM | In private preview as of April 2026 (InfoQ, GitHub announcement); may require waitlist access |
| Python asyncio.gather for parallel dispatch | HIGH | Python 3.12 stdlib documentation + multiple verified production examples |
| File-based knowledge store pattern | HIGH | Multiple industry sources, AGENTS.md research, Anthropic Skills framework alignment |
| Codex `.agents/skills/` path for skill discovery | MEDIUM | Verified from developers.openai.com/codex/skills; cross-runtime portability with Claude Code requires dual-path or symlinks |

---

## Installation

```bash
# Python runtime (3.12 recommended)
python3 -m venv .venv && source .venv/bin/activate

# Core SDK
pip install claude-agent-sdk

# CLI loop dependencies
pip install pydantic typer rich python-dotenv

# Optional: OpenTelemetry for observability
pip install claude-agent-sdk[otel]

# GitHub CLI (system package)
brew install gh        # macOS
sudo apt install gh    # Ubuntu/Debian

# gh-stack extension (if available)
gh extension install github/gh-stack

# Linear MCP transport (no install — runs via npx at agent startup)
# npx -y mcp-remote https://mcp.linear.app/mcp
```

**Environment variables:**
```bash
ANTHROPIC_API_KEY=<key>        # Required for Agent SDK
LINEAR_API_KEY=<key>           # For headless Linear MCP auth (alternative to OAuth)
GITHUB_TOKEN=<token>           # For gh CLI in non-interactive environments
```

---

## Sources

- [Claude Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) — official, accessed May 2026
- [Claude Agent SDK on PyPI](https://pypi.org/project/claude-agent-sdk/) — version 0.1.73, May 2026
- [Claude Code Skills documentation](https://code.claude.com/docs/en/skills) — full frontmatter spec
- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams) — experimental status, limitations
- [Linear MCP server docs](https://linear.app/docs/mcp) — official setup
- [Linear MCP changelog](https://linear.app/changelog/2025-05-01-mcp) — launch date May 2025
- [GitHub Stacked PRs (gh-stack)](https://github.github.com/gh-stack/) — official extension docs
- [GitHub InfoQ announcement](https://www.infoq.com/news/2026/04/github-stacked-prs/) — private preview status
- [Codex CLI Skills](https://developers.openai.com/codex/skills) — .agents/skills/ path
- [Agent Skills open standard](https://agentskills.io) — cross-runtime SKILL.md format
